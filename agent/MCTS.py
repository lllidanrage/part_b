import math
import random
import time
import sys
import os
from collections import defaultdict, deque  # 导入 deque
from copy import deepcopy

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from referee.game import Direction, MoveAction, GrowAction, IllegalActionException, BOARD_N, Board, Coord
from referee.game.player import PlayerColor
from referee.game.board import CellState


class Node:
    __slots__ = ("state", "parent", "children", "total_rewards",
                "visits", "unexplored_actions")
                
    def __init__(self, state, parent=None):
        self.state = state
        self.parent = parent
        self.children = []
        self.total_rewards = [0.0, 0.0]  # red, blue
        self.visits = 0
        # get_legal_actions 已返回有序列表，使用 list 并通过 pop() 从末尾取元素
        self.unexplored_actions = state.get_legal_actions()

    def select_child(self):
        """
        Select the child with the highest UCB1 value.
        优化UCB公式，增加对向前跳跃的偏好
        """
        # 如果没有子节点，返回自身
        if not self.children:
            return self
            
        exploration_constant = 1.414  # 标准UCB常数

        current_player = 0 if self.state.board.turn_color == PlayerColor.RED else 1

        def ucb(child) -> float:
            if child.visits == 0:
                return float('inf')
                
            # 基础UCB公式
            basic_ucb = (child.total_rewards[current_player] / child.visits +
                    exploration_constant * math.sqrt(math.log(self.visits) / child.visits))
            
            # 向前跳跃偏好
            direction_bonus = 0.0
            # 向中心跳跃偏好
            center_bonus = 0.0
            
            # 检查最后一步动作是否存在
            if hasattr(child.state, 'last_move') and child.state.last_move:
                action = child.state.last_move
                
                # 检查是否是移动动作
                if isinstance(action, MoveAction):
                    # 计算最终落点
                    final_coord = action.coord
                    for step_direction in action.directions:
                        final_coord += step_direction

                    # 1. 向前跳跃偏好
                    if len(action.directions) == 1: # 仅为单步移动或单次跳跃增加方向奖励
                        direction = action.directions[0]
                    if self.state.board.turn_color == PlayerColor.RED:
                        if direction in [Direction.Down, Direction.DownLeft, Direction.DownRight]:
                            direction_bonus = 0.1  # 红方向下移动奖励
                    elif self.state.board.turn_color == PlayerColor.BLUE:
                        if direction in [Direction.Up, Direction.UpLeft, Direction.UpRight]:
                            direction_bonus = 0.1  # 蓝方向上移动奖励
            
                    # 2. 向中心跳跃偏好
                    # 定义中心区域边界 (例如，对于8x8棋盘，是第2,3,4,5行/列)
                    # BOARD_N 通常是 8 for Freckers
                    center_lower_bound = BOARD_N // 4  # e.g., 8 // 4 = 2
                    center_upper_bound = BOARD_N - 1 - (BOARD_N // 4) # e.g., 7 - 2 = 5

                    # 判断是否为水平移动 (起始行和最终行相同)
                    is_horizontal_move = (action.coord.r == final_coord.r)

                    if not is_horizontal_move and \
                       (center_lower_bound <= final_coord.r <= center_upper_bound and 
                        center_lower_bound <= final_coord.c <= center_upper_bound):
                        center_bonus = 0.05 # 向中心移动或跳跃的奖励值，可以调整 (不包括纯水平移动)
            
            return basic_ucb + direction_bonus + center_bonus

        return max(self.children, key=ucb)

    def expand(self):
        while self.unexplored_actions:
            action = self.unexplored_actions.pop() # 使用 pop() 从列表末尾取元素
            try:
                next_state = self.state.move(action)
                child = Node(next_state, parent=self)
                self.children.append(child)
                return child
            except ValueError:  # 非法动作，直接丢弃换下一个
                # print(f"Warning: Illegal action {action} encountered during expansion. Skipping.") # for debugging
                continue
        return self    # 如果实在没有合法子节点

    def update(self, reward):
        self.visits += 1

        if self.state.board.turn_color == PlayerColor.RED:
            self.total_rewards[0] += reward
            self.total_rewards[1] -= reward
        else:
            self.total_rewards[1] += reward
            self.total_rewards[0] -= reward


class MCTS:
    """
    蒙特卡洛树搜索算法实现
    
    优先级说明:
    1000: 优先级①  - 终结胜局（到达对面边界且非起点已在边界）
    500:  优先级②  - 单蛙冲线（距离目标边界不超过2步且向目标前进）
    300:  优先级③  - 多跳推进（行数变化>=2的向前跳跃）
    200:  优先级④  - 离群棋子的向前跳跃
    190:  优先级⑤  - 开局阶段: 显著改善线形的跳跃
    180:  优先级⑥  - 开局阶段: 显著改善线形的移动
    160:  优先级⑦  - 开局阶段: 提高孤立棋子紧凑度的跳跃
    150:  优先级⑧  - 平推前线（普通向前跳跃）
    140:  优先级⑨  - 开局阶段: 轻微改善线形的跳跃
    130:  优先级⑩  - 开局阶段: 轻微改善线形的移动
    120:  优先级⑪  - 开局阶段: GROW能改善阵型
    100:  优先级⑫  - 造桥补路（创造跳跃机会的GROW）
    55:   优先级⑬  - 阻断对手（开局孤立棋子改善紧凑度）
    50:   优先级⑭  - GROW动作（默认） / 普通向前移动
    40:   优先级⑮  - 防堵自己（避免断路）
    30:   优先级⑯  - 非向前跳跃（有连跳潜力）/ 离群棋子移动且提高紧凑度
    20:   优先级⑰  - 离群棋子移动
    10:   优先级⑱  - 默认行动
    1:    优先级⑲  - 无连跳潜力的水平跳跃 / 非向前普通移动
    0.5:  优先级⑳  - 终点线无效腾挪 (新，棋子已在终点线且移动/跳跃后仍在该终点线)
    """
    def __init__(self, state, use_minimax=True, minimax_depth=3):
        self.root = Node(state)  # Node.__init__ 内部会处理 unexplored_actions
        self.use_minimax = use_minimax  # 是否使用Minimax进行模拟
        self.minimax_depth = minimax_depth  # 增加Minimax搜索深度默认值

    def search(self, iterations: int = 30):
        # ---------- 固定开局检查 ----------
        if self.root.state.should_use_fixed_opening():
            fixed_move = self.root.state.get_fixed_opening_move()
            if fixed_move is not None:
                # ① 当前颜色的固定步计数 +1
                if self.root.state.board.turn_color == PlayerColor.RED:
                    self.root.state._red_fixed_moves += 1
                    # ② 同步到棋盘，供下一回合新的 GameState 读取
                    self.root.state.board._red_fixed_moves = self.root.state._red_fixed_moves
                else:
                    self.root.state._blue_fixed_moves += 1
                    self.root.state.board._blue_fixed_moves = self.root.state._blue_fixed_moves

                # 记录在根节点，方便 UCB 偏好等逻辑使用（可选）
                self.root.state.last_move = fixed_move
                return fixed_move
        # ---------- 正常 MCTS ----------
        for _ in range(iterations):
            leaf  = self.select()
            value = self.simulate(leaf)
            self.backpropagation(leaf, value)

        if not self.root.children:          # 终局节点
            return None
        
        # 确定当前玩家索引 (0 for RED, 1 for BLUE)
        current_player_index = 0 if self.root.state.board.turn_color == PlayerColor.RED else 1
        
        best_child = max(self.root.children, 
                         key=lambda n: n.total_rewards[current_player_index] / (n.visits or 1)
                        )
        return best_child.state.last_move

    def select(self):
        current = self.root
        while not current.state.is_terminal():
            if current.unexplored_actions:
                return current.expand()
            elif not current.children:
                # 如果没有未探索的动作，也没有子节点，直接返回当前节点
                return current
            else:
                current = current.select_child()
        return current

    def simulate(self, node):
        if self.use_minimax:
            # 使用Minimax进行模拟
            return self.minimax_simulation(node.state, self.minimax_depth)
        else:
            # 改进的随机模拟，优先选择向前跳跃动作
            return self.random_simulation(node.state)
    
    def minimax_simulation(self, state, depth):
        """使用Minimax算法进行模拟，应用策略表的优先级"""
        # 获取可能的动作
        legal_actions_set = state.get_legal_actions()
        if not legal_actions_set:
            return state.get_reward()
            
        # 将集合转换为列表并评估优先级
        legal_actions = []
        action_priorities = {}
        
        for action in legal_actions_set:
            priority = 1  # 默认最低优先级
            
            if isinstance(action, MoveAction):
                init_coord = action.coord
                directions = action.directions
                final_coord = init_coord
                
                for direction in directions:
                    final_coord += direction
                
                # 优先级①: 终结胜局
                if ((state.board.turn_color == PlayerColor.RED and final_coord.r == BOARD_N - 1) or
                    (state.board.turn_color == PlayerColor.BLUE and final_coord.r == 0)):
                    priority = 1000  # 最高优先级
                    
                # 优先级②: 单蛙冲线
                distance_to_goal = 0
                if state.board.turn_color == PlayerColor.RED:
                    distance_to_goal = BOARD_N - 1 - init_coord.r
                    if distance_to_goal <= 2 and final_coord.r > init_coord.r:
                        priority = max(priority, 500)
                else:  # BLUE
                    distance_to_goal = init_coord.r
                    if distance_to_goal <= 2 and final_coord.r < init_coord.r:
                        priority = max(priority, 500)
                
                # 计算棋子与其他己方棋子的紧凑度
                try:
                    current_cohesion = self._calculate_cohesion_score(state, state.board.turn_color, init_coord)
                    final_cohesion = self._calculate_cohesion_score(state, state.board.turn_color, final_coord)
                    
                    # 检查是否是离群棋子
                    is_isolated = current_cohesion < 0.3  # 紧凑度低于0.3认为是离群棋子
                    improves_cohesion = final_cohesion > current_cohesion  # 移动后紧凑度增加
                except:
                    # 如果计算紧凑度失败，设为默认值
                    is_isolated = False
                    improves_cohesion = False
                
                # 计算行数变化
                row_change = abs(final_coord.r - init_coord.r)
                
                # 判断是否是向前跳跃
                is_forward = False
                if ((state.board.turn_color == PlayerColor.RED and final_coord.r > init_coord.r) or
                    (state.board.turn_color == PlayerColor.BLUE and final_coord.r < init_coord.r)):
                    is_forward = True
                
                # 检查是否是跳跃动作
                is_jump = False
                jump_target = None
                if len(directions) == 1:
                    direction = directions[0]
                    next_coord = init_coord + direction
                    try:
                        if state.board[next_coord].state in (PlayerColor.RED, PlayerColor.BLUE):
                            jump_target = next_coord + direction
                            if (jump_target.r >= 0 and jump_target.r < BOARD_N and 
                                jump_target.c >= 0 and jump_target.c < BOARD_N and
                                state.board[jump_target].state == "LilyPad"):
                                is_jump = True
                    except (ValueError, IndexError, KeyError, AttributeError):
                        pass
                
                if is_jump:
                    # 跳跃动作
                    if is_forward:
                        # 优先级③: 多跳推进
                        if row_change >= 2:
                            priority = max(priority, 300)
                        elif is_isolated and improves_cohesion:
                            # 离群棋子的向前跳跃
                            priority = max(priority, 120)
                        else:
                            # 优先级⑥: 平推前线
                            priority = max(priority, 100)
                    else:
                        # 水平跳跃 - 检查是否有连跳潜力
                        has_chain_potential = False
                        
                        # 检查从跳跃目标位置是否存在后续的跳跃机会
                        if jump_target:
                            next_directions = []
                            if state.board.turn_color == PlayerColor.RED:
                                next_directions = [
                                    Direction.Down,
                                    Direction.DownLeft,
                                    Direction.DownRight
                                ]
                            else:  # BLUE
                                next_directions = [
                                    Direction.Up,
                                    Direction.UpLeft,
                                    Direction.UpRight
                                ]
                            
                            for next_dir in next_directions:
                                try:
                                    next_jump_over = jump_target + next_dir
                                    if (next_jump_over.r >= 0 and next_jump_over.r < BOARD_N and 
                                        next_jump_over.c >= 0 and next_jump_over.c < BOARD_N and
                                        state.board[next_jump_over].state in (PlayerColor.RED, PlayerColor.BLUE)):
                                        
                                        next_jump_target = next_jump_over + next_dir
                                        if (next_jump_target.r >= 0 and next_jump_target.r < BOARD_N and 
                                            next_jump_target.c >= 0 and next_jump_target.c < BOARD_N and
                                            state.board[next_jump_target].state == "LilyPad"):
                                            
                                            has_chain_potential = True
                                            break
                                except (ValueError, IndexError, KeyError, AttributeError):
                                    continue
                        
                        if is_isolated and improves_cohesion:
                            # 离群棋子移动且提高紧凑度
                            priority = max(priority, 30)
                        elif has_chain_potential:
                            # 有连跳潜力的水平跳跃
                            priority = max(priority, 30)
                        # 无连跳潜力的水平跳跃保持最低优先级1
                elif is_forward:
                    # 普通向前移动
                    if is_isolated and improves_cohesion:
                        # 离群棋子移动且提高紧凑度
                        priority = max(priority, 30)
                    else:
                        priority = 1  # 最低优先级
                    
            elif isinstance(action, GrowAction):
                # 优先级④,⑤,⑦: 造桥补路、阻断对手、防堵自己
                priority = 55  # 中等优先级(在5和6之间)
            
            action_priorities[action] = priority
            legal_actions.append(action)
        
        # 根据优先级排序
        sorted_actions = sorted(legal_actions, key=lambda a: action_priorities[a], reverse=True)
        
        # 取优先级最高的几个动作
        max_actions_to_consider = 8
        pruned_actions = sorted_actions[:max_actions_to_consider]
        
        # 进行Minimax搜索
        return self.minimax(state, min(depth, 3), float('-inf'), float('inf'), True, pruned_actions)
        
    def minimax(self, state, depth, alpha, beta, maximizing_player, priority_actions=None):
        """使用Alpha-Beta剪枝的Minimax算法，可选择性地只考虑优先动作"""
        # 如果达到终止条件（终止状态或达到最大深度）
        if depth == 0 or state.is_terminal():
            return state.get_reward()
        
        # 确定要考虑的动作列表
        if priority_actions is not None and priority_actions:
            actions_to_consider = priority_actions
        else:
            legal_actions_set = state.get_legal_actions()
            if not legal_actions_set:
                return state.get_reward()
            
            actions_to_consider = []
            for action in legal_actions_set:
                actions_to_consider.append(action)
        
        if maximizing_player:
            value = float('-inf')
            # 遍历所有合法动作
            for action in actions_to_consider:
                try:
                    next_state = state.move(action)
                    new_value = self.minimax(next_state, depth - 1, alpha, beta, False)
                    value = max(value, new_value)
                    alpha = max(alpha, value)
                    if beta <= alpha:
                        break  # Beta剪枝
                except Exception as e:
                    # 处理可能的异常（如非法动作）
                    continue
            return value
        else:
            value = float('inf')
            # 遍历所有合法动作
            for action in actions_to_consider:
                try:
                    next_state = state.move(action)
                    new_value = self.minimax(next_state, depth - 1, alpha, beta, True)
                    value = min(value, new_value)
                    beta = min(beta, value)
                    if beta <= alpha:
                        break  # Alpha剪枝
                except Exception as e:
                    # 处理可能的异常（如非法动作）
                    continue
            return value
    
    def random_simulation(self, state):
        """根据策略表的优先级进行模拟"""
        current_state = state
        simulation_count = 10  # 模拟步数
        
        while not current_state.is_terminal() and simulation_count > 0:
            legal_actions = current_state.get_legal_actions()
            if not legal_actions:
                break
            
            # 根据优先级分类动作
            priority_actions = {
                1000: [],  # 优先级①: 终结胜局
                500: [],   # 优先级②: 单蛙冲线
                300: [],   # 优先级③: 多跳推进
                200: [],   # 优先级④: 离群棋子的向前跳跃 (新)
                190: [],   # 优先级⑤: 开局阶段: 显著改善线形的跳跃
                180: [],   # 优先级⑥: 开局阶段: 显著改善线形的移动
                160: [],   # 优先级⑦: 开局阶段: 提高孤立棋子紧凑度的跳跃
                150: [],   # 优先级⑧: 平推前线（普通向前跳跃） (原100)
                140: [],   # 优先级⑨: 开局阶段: 轻微改善线形的跳跃
                130: [],   # 优先级⑩: 开局阶段: 轻微改善线形的移动
                120: [],   # 优先级⑪: 开局阶段: GROW能改善阵型
                100: [],   # 优先级⑫: 造桥补路（创造跳跃机会的GROW）(原200)
                55: [],    # 优先级⑬: 阻断对手（开局孤立棋子改善紧凑度）(原100)
                50: [],    # 优先级⑭: GROW动作（默认）(原55) / 普通向前移动 (原50)
                40: [],    # 优先级⑮: 防堵自己（避免断路）
                30: [],    # 优先级⑯: 非向前跳跃（有连跳潜力）/ 离群棋子移动且提高紧凑度
                20: [],    # 优先级⑰: 离群棋子移动
                10: [],    # 优先级⑱: 默认行动
                1: [],     # 优先级⑲: 无连跳潜力的水平跳跃 / 非向前普通移动
                0.5: []    # 优先级⑳: 终点线无效腾挪
            }
            
            # 评估每个动作
            for action in legal_actions:
                if isinstance(action, MoveAction):
                    init_coord = action.coord
                    directions = action.directions
                    final_coord = init_coord
                    
                    for direction in directions:
                        final_coord += direction
                    
                    # 优先级①: 终结胜局
                    if ((current_state.board.turn_color == PlayerColor.RED and final_coord.r == BOARD_N - 1) or
                        (current_state.board.turn_color == PlayerColor.BLUE and final_coord.r == 0)):
                        priority_actions[1000].append(action)
                        continue
                    
                    # 优先级②: 单蛙冲线 - 接近终点的移动
                    distance_to_goal = 0
                    if current_state.board.turn_color == PlayerColor.RED:
                        distance_to_goal = BOARD_N - 1 - init_coord.r
                        if distance_to_goal <= 2 and final_coord.r > init_coord.r:
                            priority_actions[500].append(action)
                            continue
                    else:  # BLUE
                        distance_to_goal = init_coord.r
                        if distance_to_goal <= 2 and final_coord.r < init_coord.r:
                            priority_actions[500].append(action)
                            continue
                    
                    # 计算行数变化
                    row_change = abs(final_coord.r - init_coord.r)
                    
                    # 判断是否是向前跳跃
                    is_forward = False
                    if ((current_state.board.turn_color == PlayerColor.RED and final_coord.r > init_coord.r) or
                        (current_state.board.turn_color == PlayerColor.BLUE and final_coord.r < init_coord.r)):
                        is_forward = True
                    
                    # 检查是否是跳跃动作
                    is_jump = False
                    jump_target = None
                    if len(directions) == 1:
                        direction = directions[0]
                        next_coord = init_coord + direction
                        try:
                            if (next_coord.r >= 0 and next_coord.r < BOARD_N and 
                                next_coord.c >= 0 and next_coord.c < BOARD_N and
                                current_state.board[next_coord].state in (PlayerColor.RED, PlayerColor.BLUE)):
                                
                                jump_target = next_coord + direction
                                if (jump_target.r >= 0 and jump_target.r < BOARD_N and 
                                    jump_target.c >= 0 and jump_target.c < BOARD_N and
                                    current_state.board[jump_target].state == "LilyPad"):
                                    
                                    # 检查是否是向前连跳
                                    if ((current_state.board.turn_color == PlayerColor.RED and 
                                        next_dir in [Direction.Down, Direction.DownLeft, Direction.DownRight]) or
                                        (current_state.board.turn_color == PlayerColor.BLUE and 
                                        next_dir in [Direction.Up, Direction.UpLeft, Direction.UpRight])):
                                        
                                        # 有向前连跳潜力
                                        has_chain_potential = True
                                        break
                        except (ValueError, IndexError, KeyError):
                            pass
                    
                    if is_jump:
                        # 跳跃动作
                        if is_forward:
                            # 优先级③: 多跳推进 - 行数变化大的向前跳跃
                            if row_change >= 2:
                                priority_actions[300].append(action)
                            else:
                                # 优先级⑥: 平推前线 - 普通向前跳跃
                                priority_actions[100].append(action)
                        else:
                            # 水平跳跃 - 检查是否有连跳潜力
                            has_chain_potential = False
                            
                            # 获取可能的连跳方向
                            next_directions = []
                            if current_state.board.turn_color == PlayerColor.RED:
                                next_directions = [
                                    Direction.Down,
                                    Direction.DownLeft,
                                    Direction.DownRight,
                                    Direction.Left,
                                    Direction.Right
                                ]
                            else:  # BLUE
                                next_directions = [
                                    Direction.Up,
                                    Direction.UpLeft,
                                    Direction.UpRight,
                                    Direction.Left,
                                    Direction.Right
                                ]
                            
                            # 检查从跳跃目标位置是否存在后续的跳跃机会
                            for next_dir in next_directions:
                                try:
                                    next_jump_over = jump_target + next_dir
                                    # 检查下一个位置是否有棋子
                                    if (next_jump_over.r >= 0 and next_jump_over.r < BOARD_N and 
                                        next_jump_over.c >= 0 and next_jump_over.c < BOARD_N and
                                        current_state.board[next_jump_over].state in (PlayerColor.RED, PlayerColor.BLUE)):
                                        
                                        # 检查跳过这个棋子后的位置是否是荷叶
                                        next_jump_target = next_jump_over + next_dir
                                        if (next_jump_target.r >= 0 and next_jump_target.r < BOARD_N and 
                                            next_jump_target.c >= 0 and next_jump_target.c < BOARD_N and
                                            current_state.board[next_jump_target].state == "LilyPad"):
                                            
                                            # 检查是否是向前跳跃
                                            if ((current_state.board.turn_color == PlayerColor.RED and 
                                                next_dir in [Direction.Down, Direction.DownLeft, Direction.DownRight]) or
                                                (current_state.board.turn_color == PlayerColor.BLUE and 
                                                next_dir in [Direction.Up, Direction.UpLeft, Direction.UpRight])):
                                                
                                                # 有向前连跳潜力
                                                has_chain_potential = True
                                                break
                                except (ValueError, IndexError, KeyError):
                                    continue
                            
                            if has_chain_potential:
                                # 优先级⑧: 有连跳潜力的水平跳跃
                                priority_actions[30].append(action)
                            else:
                                # 优先级⑩: 无连跳潜力的水平跳跃
                                priority_actions[1].append(action)
                elif isinstance(action, GrowAction):
                    # GROW动作 - 给它中等优先级(在5和6之间)
                    priority_actions[55].append(action)
            
            # 根据优先级选择动作
            selected_action = None
            
            # 从高到低优先级选择
            for priority in sorted(priority_actions.keys(), reverse=True):
                if priority_actions[priority]:
                    # 在该优先级中随机选择，增加一些多样性
                    selected_action = random.choice(priority_actions[priority])
                    break
            
            if not selected_action and legal_actions:
                # 兜底 - 随机选择任意合法动作
                selected_action = random.choice(list(legal_actions))
            
            # 执行选中的动作
            try:
                current_state = current_state.move(selected_action)
                simulation_count -= 1
            except ValueError:
                continue
                
        return current_state.get_reward()

    def backpropagation(self, node, reward):
        while node:
            node.update(reward)
            node = node.parent
        return


class GameState:
    def __init__(self, last_move, board):
        self.last_move = last_move
        self.board = board
        self._turn_count = board.turn_count

        # 确保棋盘对象自带计数字段
        if not hasattr(board, "_red_fixed_moves"):
            board._red_fixed_moves = 0
        if not hasattr(board, "_blue_fixed_moves"):
            board._blue_fixed_moves = 0

        self._red_fixed_moves = board._red_fixed_moves
        self._blue_fixed_moves = board._blue_fixed_moves
        
        # 维护己方青蛙位置列表
        self.my_frogs = []
        self._update_my_frogs()
        
    def _update_my_frogs(self):
        """更新己方青蛙位置列表"""
        self.my_frogs = []
        for r in range(BOARD_N):
            for c in range(BOARD_N):
                coord = Coord(r, c)
                try:
                    if self.board[coord].state == self.board.turn_color:
                        self.my_frogs.append(coord)
                except (ValueError, KeyError):
                    continue
        
    def is_opening_phase(self):
        """判断当前是否处于开局阶段（前30个回合）"""
        return self._turn_count < 30
        
    def should_use_fixed_opening(self):
        """判断是否应该使用固定开局"""
        if self._turn_count >= 15:  # 前15回合使用固定开局
            return False
            
        # 因为总共15回合，一方7步，一方8步，或者根据实际情况调整
        # 这里假设红方先手，可能走8步，蓝方走7步
        if self.board.turn_color == PlayerColor.RED:
            return self._red_fixed_moves < 7 
        else:
            return self._blue_fixed_moves < 7
        
    def get_fixed_opening_move(self):
        """获取固定开局的动作"""
        if self.board.turn_color == PlayerColor.RED:
            # 红方固定开局：(0,2)向下、(0,5)向下、GROW
            if self._red_fixed_moves == 0:
                source = Coord(0, 2)
                direction = Direction.Down
                return MoveAction(source, (direction,))
                        
            elif self._red_fixed_moves == 1:
                source = Coord(0, 5)
                direction = Direction.Down
                return MoveAction(source, (direction,))
                        
            elif self._red_fixed_moves == 2:
                return GrowAction()
            elif self._red_fixed_moves == 3:  # 第4步
                # 示例：红方第四步，例如 (1,2) 向下
                source = Coord(0,1)
                direction = Direction.DownRight
                return MoveAction(source, (direction,))
            elif self._red_fixed_moves == 4:  # 第5步
                # 示例：红方第五步，例如 (1,5) 向下
                source = Coord(0, 6)
                direction = Direction.DownLeft
                return MoveAction(source, (direction,))
            elif self._red_fixed_moves == 5:
                source = Coord(0, 4)
                return MoveAction(source, (Direction.Left,Direction.Down))
            elif self._red_fixed_moves == 6:
                source = Coord(0, 3)
                return MoveAction(source, (Direction.DownLeft,))
        else:  # BLUE
            # 蓝方固定开局：(7,2)向上、(7,5)向上、GROW
            if self._blue_fixed_moves == 0:
                source = Coord(7, 2)
                direction = Direction.Up
                return MoveAction(source, (direction,))
                        
            elif self._blue_fixed_moves == 1:
                source = Coord(7, 5)
                direction = Direction.Up
                return MoveAction(source, (direction,))
                        
            elif self._blue_fixed_moves == 2:
                return GrowAction()
            elif self._blue_fixed_moves == 3:  # 第4步
                # 示例：蓝方第四步，例如 (6,2) 向上
                source = Coord(7, 1)
                direction = Direction.UpRight
                return MoveAction(source, (direction,))
            elif self._blue_fixed_moves == 4:  # 第5步
                # 示例：蓝方第五步，例如 (6,5) 向上
                source = Coord(7, 6)
                direction = Direction.UpLeft
                return MoveAction(source, (direction,))
            elif self._blue_fixed_moves == 5:
                source = Coord(7, 3)
                return MoveAction(source, (Direction.Right,Direction.Up))
            elif self._blue_fixed_moves == 6:
                source = Coord(7, 4)
                return MoveAction(source, (Direction.UpRight,))
        return None

    def get_legal_actions(self):
        """获取合法动作，使用优化的青蛙列表"""
        # 尝试使用固定开局策略
        if self.should_use_fixed_opening():
            fixed_move = self.get_fixed_opening_move()
            if fixed_move is not None:
                return {fixed_move}
        
        actions = defaultdict(set)
        
        # 只遍历己方青蛙列表，而不是整个棋盘
        for coord in self.my_frogs:
            # 检查所有可能的移动方向
            for direction in [Direction.Up, Direction.Down, 
                            Direction.Left, Direction.Right,
                            Direction.UpLeft, Direction.UpRight,
                            Direction.DownLeft, Direction.DownRight]:
                # 尝试移动
                try:
                    move_action = MoveAction(coord, (direction,))
                    test_board = self.board.clone()
                    test_board.apply_action(move_action)
                    
                    # 判断是否是向前移动
                    is_forward = False
                    if self.board.turn_color == PlayerColor.RED:
                        if direction in [Direction.Down, Direction.DownLeft, Direction.DownRight]:
                            is_forward = True
                    else:  # BLUE
                        if direction in [Direction.Up, Direction.UpLeft, Direction.UpRight]:
                            is_forward = True
                    
                    # 添加普通移动
                    if is_forward:
                        actions[50].add(move_action)  # 向前移动
                    else:
                        actions[1].add(move_action)  # 非向前移动
                except (ValueError, IllegalActionException):
                    continue
                
                # 检查是否可以跳跃（只有当存在相邻棋子时才尝试）
                next_coord = coord + direction
                try:
                    if (0 <= next_coord.r < BOARD_N and 
                        0 <= next_coord.c < BOARD_N and 
                        self.board[next_coord].state in (PlayerColor.RED, PlayerColor.BLUE)):
                        
                        jump_target = next_coord + direction
                        if (0 <= jump_target.r < BOARD_N and 
                            0 <= jump_target.c < BOARD_N and 
                            self.board[jump_target].state == "LilyPad"):
                            
                            jump_action = MoveAction(coord, (direction, direction))
                            try:
                                # 验证跳跃是否合法
                                test_board = self.board.clone()
                                test_board.apply_action(jump_action)
                                
                                # 判断是否是向前跳跃
                                is_forward = False
                                if self.board.turn_color == PlayerColor.RED:
                                    if jump_target.r > coord.r:
                                        is_forward = True
                                else:  # BLUE
                                    if jump_target.r < coord.r:
                                        is_forward = True
                                        
                                if is_forward:
                                    # 计算行数变化
                                    row_change = abs(jump_target.r - coord.r)
                                    if row_change >= 2:
                                        # 优先级③: 多跳推进
                                        actions[300].add(jump_action)
                                    else:
                                        # 优先级⑧: 平推前线
                                        actions[150].add(jump_action)
                                else:
                                    # 只有向前跳跃时才检查连跳潜力，否则直接赋予低优先级
                                    has_chain_potential = self._check_chain_jump_potential(jump_target)
                                    if has_chain_potential:
                                        # 优先级⑨: 有连跳潜力的非向前跳跃
                                        actions[30].add(jump_action)
                                    else:
                                        # 优先级⑫: 无连跳潜力的水平跳跃
                                        actions[1].add(jump_action)
                            except (ValueError, IllegalActionException):
                                continue
                except (ValueError, KeyError, IndexError):
                    continue
        
        # 检查GROW动作是否合法
        try:
            grow_action = GrowAction()
            test_board = self.board.clone()
            test_board.apply_action(grow_action)
            actions[55].add(grow_action)  # GROW动作优先级为55
        except (ValueError, IllegalActionException):
            pass
        
        # 合并所有优先级的动作
        all_actions = set()
        for priority in sorted(actions.keys(), reverse=True):
            all_actions.update(actions[priority])
        
        return all_actions
        
    def _check_chain_jump_potential(self, coord):
        """检查从给定位置是否有连跳的潜力"""
        # 获取可能的跳跃方向
        if self.board.turn_color == PlayerColor.RED:
            directions = [Direction.Down, Direction.DownLeft, Direction.DownRight]
        else:  # BLUE
            directions = [Direction.Up, Direction.UpLeft, Direction.UpRight]
            
        # 检查每个方向
        for direction in directions:
            next_coord = coord + direction
            if (0 <= next_coord.r < BOARD_N and 
                0 <= next_coord.c < BOARD_N and 
                self.board[next_coord].state in (PlayerColor.RED, PlayerColor.BLUE)):
                
                jump_target = next_coord + direction
                if (0 <= jump_target.r < BOARD_N and 
                    0 <= jump_target.c < BOARD_N and 
                    self.board[jump_target].state == "LilyPad"):
                    return True
                    
        return False

    def move(self, action):
        new_board = self.board.clone() # 使用 clone() 替换 deepcopy()
        try:
            new_board.apply_action(action)
            # 创建新的 GameState，并传递 action 作为 last_move
            new_state = GameState(action, new_board)
            # 不需要显式调用_update_my_frogs，因为在GameState的__init__中已经调用了
            return new_state 
        except IllegalActionException as e:
            # 将 referee 的 IllegalActionException 包装成 ValueError 或直接重抛，以便 MCTS 的 expand 捕获
            # 或者，如果 MCTS.expand() 直接捕获 IllegalActionException，则无需转换
            # 根据您的方案，MCTS.expand 将捕获 ValueError
            # print(f"Illegal action in GameState.move: {action} -> {e}") # for debugging
            raise ValueError(f"Illegal action: {e}") from e

    def is_terminal(self):
        return self.board.game_over

    def get_reward(self):
        """优化的评估函数，根据策略表考虑优先级因素"""
        if self.is_terminal():
            red_score = self.board._player_score(PlayerColor.RED)
            blue_score = self.board._player_score(PlayerColor.BLUE)

            if self.board.turn_color == PlayerColor.RED:
                return 1.0 if red_score > blue_score else \
                    (-1.0 if red_score < blue_score else 0.0)
            else:
                return 1.0 if blue_score > red_score else \
                    (-1.0 if blue_score < red_score else 0.0)
        else:
            # 评估各项因素
            score = 0.0
            
            # 1. 棋子在终点行的数量 - 优先级①②
            red_goal_count = self.board._row_count(PlayerColor.RED, BOARD_N - 1)
            blue_goal_count = self.board._row_count(PlayerColor.BLUE, 0)
            goal_weight = 5.0  # 终点行的棋子权重最高
            
            # 2. 接近终点的棋子 - 优先级②
            red_near_goal = 0
            blue_near_goal = 0
            
            # 3. 棋子整体推进程度 - 优先级③⑥
            red_progress = 0
            blue_progress = 0
            red_pieces = 0
            blue_pieces = 0
            
            # 4. 跳跃机会 - 优先级③④
            red_jumps = self._count_jump_opportunities(PlayerColor.RED)
            blue_jumps = self._count_jump_opportunities(PlayerColor.BLUE)
            
            # 计算棋子分布和推进情况
            for coord, cell in self.board._state.items():
                if cell.state == PlayerColor.RED:
                    # 红方棋子
                    red_pieces += 1
                    # 推进程度 - 行号越高越好
                    red_progress += coord.r
                    # 接近终点 - 距离终点小于等于2行
                    if BOARD_N - 1 - coord.r <= 2:
                        red_near_goal += 1
                elif cell.state == PlayerColor.BLUE:
                    # 蓝方棋子
                    blue_pieces += 1
                    # 推进程度 - 行号越低越好
                    blue_progress += (BOARD_N - 1 - coord.r)
                    # 接近终点 - 距离终点小于等于2行
                    if coord.r <= 2:
                        blue_near_goal += 1
            
            # 归一化进度
            if red_pieces > 0:
                red_progress = red_progress / (red_pieces * (BOARD_N - 1))
            if blue_pieces > 0:
                blue_progress = blue_progress / (blue_pieces * (BOARD_N - 1))
            
            # 加权计算得分
            near_goal_weight = 3.0  # 接近终点的棋子
            progress_weight = 2.0   # 整体推进程度
            jump_weight = 1.5       # 跳跃机会
            
            # 综合得分
            score += (goal_weight * (red_goal_count - blue_goal_count) + 
                    near_goal_weight * (red_near_goal - blue_near_goal) +
                    progress_weight * (red_progress - blue_progress) +
                    jump_weight * (red_jumps - blue_jumps))
            
            # 根据当前回合方调整评分
            if self.board.turn_color == PlayerColor.RED:
                return score
            else:
                return -score
                
    def _count_jump_opportunities(self, player_color):
        """统计指定玩家的跳跃机会数量"""
        jump_count = 0
        
        # 获取玩家棋子位置
        player_positions = []
        for coord, cell in self.board._state.items():
            if cell.state == player_color:
                player_positions.append(coord)
                
        # 确定可用的移动方向
        directions = []
        if player_color == PlayerColor.RED:
            directions = [
                Direction.Down,
                Direction.DownLeft,
                Direction.DownRight,
                Direction.Left,
                Direction.Right
            ]
        else:  # BLUE
            directions = [
                Direction.Up,
                Direction.UpLeft,
                Direction.UpRight,
                Direction.Left,
                Direction.Right
            ]
            
        # 检查每个棋子的跳跃机会
        for coord in player_positions:
            for direction in directions:
                try:
                    # 检查是否有棋子可以跳过
                    adjacent_coord = coord + direction
                    if (adjacent_coord.r >= 0 and adjacent_coord.r < BOARD_N and 
                        adjacent_coord.c >= 0 and adjacent_coord.c < BOARD_N and
                        self.board[adjacent_coord].state in (PlayerColor.RED, PlayerColor.BLUE)):
                        
                        # 检查是否有荷叶可以跳到
                        landing_coord = adjacent_coord + direction
                        if (landing_coord.r >= 0 and landing_coord.r < BOARD_N and 
                            landing_coord.c >= 0 and landing_coord.c < BOARD_N and
                            self.board[landing_coord].state == "LilyPad"):
                            
                            # 向前跳跃额外价值
                            if (player_color == PlayerColor.RED and 
                                direction in [Direction.Down, Direction.DownLeft, Direction.DownRight]):
                                jump_count += 2  # 向前跳跃价值更高
                            elif (player_color == PlayerColor.BLUE and 
                                  direction in [Direction.Up, Direction.UpLeft, Direction.UpRight]):
                                jump_count += 2  # 向前跳跃价值更高
                            else:
                                jump_count += 1  # 水平跳跃
                except (ValueError, IndexError, KeyError):
                    continue
                    
        return jump_count

    def _calculate_cohesion_score(self, player_color, piece_coord):
        """计算一个棋子与其他己方棋子的紧凑度分数
        分数越高表示棋子与其他己方棋子越接近，越低表示棋子离群"""
        cohesion_score = 0
        
        # 收集所有己方棋子的位置
        ally_pieces = []
        for coord, cell in self.board._state.items():
            if cell.state == player_color and coord != piece_coord:
                ally_pieces.append(coord)
        
        if not ally_pieces:
            return 0  # 如果没有其他己方棋子，返回0
        
        # 计算曼哈顿距离的总和
        total_distance = 0
        for ally_coord in ally_pieces:
            # 计算曼哈顿距离 (|x1-x2| + |y1-y2|)
            distance = abs(piece_coord.r - ally_coord.r) + abs(piece_coord.c - ally_coord.c)
            total_distance += distance
        
        # 平均距离，距离越小，紧凑度越高
        avg_distance = total_distance / len(ally_pieces)
        
        # 将距离转换为分数，距离越小分数越高
        # 使用一个最大可能距离作为标准化因子(两倍棋盘大小是一个保守估计)
        max_possible_distance = 2 * BOARD_N
        cohesion_score = 1.0 - (avg_distance / max_possible_distance)
        
        return cohesion_score

    def _check_jump_bridge_formation(self, player_color, target_coord):
        """检查目标位置是否能够为其他棋子提供前进跳跃的机会
        
        返回:
            int: 可能提供的跳跃机会数，数值越大表示位置越有价值
        """
        jump_opportunities = 0
        
        # 获取所有己方棋子
        ally_pieces = []
        for coord, cell in self.board._state.items():
            if cell.state == player_color and coord != target_coord:
                ally_pieces.append(coord)
        
        if not ally_pieces:
            return 0
        
        # 确定评估方向，检查其他棋子是否可以跳过目标位置
        forward_directions = []
        if player_color == PlayerColor.RED:
            # 对于红方棋子，检查从上方来的跳跃
            check_directions = [Direction.Up, Direction.UpLeft, Direction.UpRight]
            # 前进方向是向下
            forward_directions = [Direction.Down, Direction.DownLeft, Direction.DownRight]
        else:  # BLUE
            # 对于蓝方棋子，检查从下方来的跳跃
            check_directions = [Direction.Down, Direction.DownLeft, Direction.DownRight]
            # 前进方向是向上
            forward_directions = [Direction.Up, Direction.UpLeft, Direction.UpRight]
        
        # 检查每个己方棋子是否能跳过目标位置
        for ally_coord in ally_pieces:
            for direction in check_directions:
                # 计算跳跃前的位置（即用来起跳的棋子位置）
                jump_start = target_coord - direction
                
                # 检查这个位置是否是己方棋子
                if jump_start == ally_coord:
                    # 计算跳跃后的落点
                    jump_target = target_coord + direction
                    
                    try:
                        # 检查跳跃目标位置是否有效且是荷叶（可以跳到）
                        if (jump_target.r >= 0 and jump_target.r < BOARD_N and
                            jump_target.c >= 0 and jump_target.c < BOARD_N and
                            self.board[jump_target].state == "LilyPad"):
                            
                            # 判断是否是向前跳跃（朝着目标方向）
                            if direction in forward_directions:
                                # 向前跳跃机会价值更高
                                jump_opportunities += 2
                            else:
                                # 其他方向跳跃
                                jump_opportunities += 1
                    except (ValueError, IndexError, KeyError):
                        continue
        
        return jump_opportunities


if __name__ == '__main__':
    # 创建一个测试场景，尝试执行跳跃动作
    # 使用自带的初始棋盘方法创建棋盘
    basic_board = Board()
    
    # 使用已有棋盘的方法来设置新的棋盘状态
    # 首先创建一个空荷叶棋盘
    new_board = Board()
    
    # 清除所有位置
    for r in range(BOARD_N):
        for c in range(BOARD_N):
            coord = Coord(r, c)
            # 找到一个空的CellState
            empty_cell = None
            for test_r in range(BOARD_N):
                for test_c in range(BOARD_N):
                    test_coord = Coord(test_r, test_c)
                    if test_coord in new_board._state and new_board._state[test_coord].state is None:
                        empty_cell = new_board._state[test_coord]
                        break
                if empty_cell:
                    break
            if empty_cell:
                new_board.set_cell_state(coord, empty_cell)
    
    # 放置红方棋子 - 从现有棋盘中找一个红方棋子复制过来
    red_cell = None
    for coord, cell in basic_board._state.items():
        if cell.state == PlayerColor.RED:
            red_cell = cell
            break
    
    red_coord = Coord(2, 2)
    if red_cell:
        new_board.set_cell_state(red_coord, red_cell)
    
    # 放置蓝方棋子作为跳跃障碍 - 找一个蓝方棋子
    blue_cell = None
    for coord, cell in basic_board._state.items():
        if cell.state == PlayerColor.BLUE:
            blue_cell = cell
            break
            
    blue_coord = Coord(3, 3)
    if blue_cell:
        new_board.set_cell_state(blue_coord, blue_cell)
    
    # 放置目标荷叶 - 找一个荷叶
    lily_cell = None
    for coord, cell in basic_board._state.items():
        if cell.state == "LilyPad":
            lily_cell = cell
            break
            
    lily_coord = Coord(4, 4)
    if lily_cell:
        new_board.set_cell_state(lily_coord, lily_cell)
    
    # 设置为红方回合
    new_board.set_turn_color(PlayerColor.RED)
    
    # 打印初始棋盘
    print("=== 测试MCTS-Minimax混合算法 ===")
    print("初始棋盘:")
    print(new_board.render())
    
    # 尝试运行MCTS-Minimax混合算法
    state = GameState(None, new_board)
    legal_actions = state.get_legal_actions()
    print(f"合法动作: {legal_actions}")
    
    # 使用MCTS-Minimax混合算法
    print("\n===== MCTS-Minimax混合算法 =====")
    start_time = time.time()
    mcts = MCTS(state, use_minimax=True, minimax_depth=2)
    best_action = mcts.search(iterations=30)
    minimax_time = time.time() - start_time
    print(f"耗时: {minimax_time:.2f}秒")
    print(f"最佳动作: {best_action}")
    
    # 对比传统MCTS
    print("\n===== 传统MCTS算法 =====")
    start_time = time.time()
    mcts_traditional = MCTS(state, use_minimax=False)
    best_action_traditional = mcts_traditional.search(iterations=100)
    traditional_time = time.time() - start_time
    print(f"耗时: {traditional_time:.2f}秒")
    print(f"最佳动作: {best_action_traditional}")

