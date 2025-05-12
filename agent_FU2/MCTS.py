import math
import random
import time
import sys
import os
from collections import defaultdict, deque  # 导入 deque
from copy import deepcopy

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from referee.game import Direction, MoveAction, GrowAction, IllegalActionException, BOARD_N, Board, Coord, Action
from referee.game.player import PlayerColor
from referee.game.board import CellState


class Node:
    __slots__ = ("state", "parent", "children", "total_rewards",
                "visits", "unexplored_actions")
                
    def __init__(self, state, parent=None):
        self.state = state
        self.parent = parent
        self.children = []
        self.total_rewards = 0.0  # Changed: Store as a single float, relative to root player
        self.visits = 0
        # GameState.get_legal_actions() now returns a list sorted by priority (highest first).
        # We use a deque for efficient pop from the left (highest priority).
        self.unexplored_actions = deque(state.get_legal_actions()) 

    def select_child(self, root_player_color):
        """
        Select the child with the highest UCB1 value.
        Rewards are relative to root_player_color.
        The decision at self (parent) is made by self.state.board.turn_color.
        """
        if not self.children:
            return self # Should not happen if called after ensuring children exist or unexplored_actions is empty
        
        exploration_constant = 1.414
        current_decision_maker_color = self.state.board.turn_color

        # Determine if the current decision maker is the same as the root player.
        # If so, they want to maximize child.total_rewards (which is from root's perspective).
        # If not, they are the opponent, and want to minimize child.total_rewards (from root's perspective),
        # which means maximizing -child.total_rewards.
        exploitation_coeff = 1.0 if current_decision_maker_color == root_player_color else -1.0

        def ucb(child_node) -> float:
            if child_node.visits == 0:
                return float('inf')
            
            # child_node.total_rewards is already relative to root_player_color
            exploitation_from_root_pov = child_node.total_rewards / child_node.visits
            effective_exploitation = exploitation_coeff * exploitation_from_root_pov
            
            exploration = exploration_constant * math.sqrt(math.log(self.visits) / child_node.visits)
            
            # Heuristic bonuses are from the perspective of current_decision_maker_color
            direction_bonus = 0.0
            center_bonus = 0.0
            action_to_child = child_node.state.last_move
            if action_to_child and isinstance(action_to_child, MoveAction):
                current_eval_pos = action_to_child.coord
                final_eval_coord = action_to_child.coord # Initialize final_eval_coord before the loop
                for jump_dir_segment in action_to_child.directions:
                    # 修改为此处的两行，以简化计算并处理滑动/跳跃
                    final_eval_coord = current_eval_pos + jump_dir_segment.value
                    current_eval_pos = final_eval_coord
                
                if len(action_to_child.directions) == 1:
                    direction = action_to_child.directions[0]
                    if current_decision_maker_color == PlayerColor.RED:
                        if direction in [Direction.Down, Direction.DownLeft, Direction.DownRight]: direction_bonus = 0.1
                    elif current_decision_maker_color == PlayerColor.BLUE:
                        if direction in [Direction.Up, Direction.UpLeft, Direction.UpRight]: direction_bonus = 0.1
                
                center_lower_bound = BOARD_N // 4
                center_upper_bound = BOARD_N - 1 - (BOARD_N // 4)
                is_horizontal_move = (action_to_child.coord.r == final_eval_coord.r)
                if not is_horizontal_move and \
                   (center_lower_bound <= final_eval_coord.r <= center_upper_bound and 
                    center_lower_bound <= final_eval_coord.c <= center_upper_bound):
                    center_bonus = 0.05
            return effective_exploitation + exploration + direction_bonus + center_bonus
        return max(self.children, key=ucb)

    def expand(self):
        if self.unexplored_actions:
            action = self.unexplored_actions.popleft()
            try:
                next_state = self.state.move(action)
                child = Node(next_state, parent=self)
                self.children.append(child)
                return child
            except ValueError: 
                return self.expand() 
        return self 

    def update(self, reward_increment_relative_to_root):
        self.visits += 1
        # This reward is always from the perspective of the root player.
        # The root node itself will not have its total_rewards changed by this logic in backpropagation.
        self.total_rewards += reward_increment_relative_to_root


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
    def __init__(self, state, use_minimax=True, minimax_depth=2, test_mode=False):
        self.root = Node(state)  # Node.__init__ 内部会处理 unexplored_actions
        self.use_minimax = use_minimax  # 是否使用Minimax进行模拟
        self.minimax_depth = minimax_depth  # 增加Minimax搜索深度默认值
        self.test_mode = test_mode  # 添加测试模式标志
        self.root_player_color = state.board.turn_color # Added: Store root player's color

    def search(self, iterations: int = 50):
        # ---------- 固定开局检查 ----------
        if self.root.state.should_use_fixed_opening() and not self.test_mode:
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
            leaf = self.select()
            if not leaf.unexplored_actions and not leaf.children and not leaf.state.is_terminal():
                # If leaf is non-terminal, has no children and no unexplored actions, it might be a dead end from illegal moves
                # This can happen if all expansions from it failed. Backpropagate a very bad score.
                # Or, GameState.get_legal_actions() might have returned empty for a non-terminal state.
                # For now, let's assume select finds a valid leaf or expand() handles it.
                pass 
            
            # If leaf is terminal or has no unexplored actions (but might have children), simulate from it.
            # If it has unexplored actions, expand one then simulate from the new child.
            if leaf.unexplored_actions and not leaf.state.is_terminal():
                child_leaf = leaf.expand()
                if child_leaf != leaf: 
                    sim_reward = self.simulate(child_leaf) # sim_reward is from child_leaf's perspective (whose turn it is there)
                    self.backpropagation(child_leaf, sim_reward)
                else: 
                    sim_reward = self.simulate(leaf) 
                    self.backpropagation(leaf, sim_reward)
            else:
                 sim_reward = self.simulate(leaf)
                 self.backpropagation(leaf, sim_reward)

        if not self.root.children:          # 终局节点
            return None
        
        # Debug: Print root children stats
        print("\n--- Root Children Stats ---")
        # Rewards in children are already relative to self.root_player_color
        # The root player (self.root_player_color) wants to maximize these rewards.
        for child in self.root.children:
            act = child.state.last_move
            if child.visits > 0:
                mean_reward = child.total_rewards / child.visits # child.total_rewards is relative to root player
            else:
                mean_reward = 0.0 
            print(f"{str(act):<40}  visits={child.visits:<3}  mean_reward={mean_reward:+.3f}")
        print("---------------------------")

        # Final selection based on rewards for the root player.
        # child.total_rewards is already from the root player's perspective.
        best_child = max(self.root.children, 
                         key=lambda n: n.total_rewards / (n.visits or 1))
        return best_child.state.last_move

    def select(self):
        current = self.root
        while not current.state.is_terminal():
            if current.unexplored_actions:
                return current 
            elif not current.children: 
                return current # Should be a terminal node or a node that couldn't expand
            else:
                current = current.select_child(self.root_player_color) # Pass root_player_color
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
                    # 跳跃动作处理
                    if is_forward:
                        # 优先级③: 多跳推进
                        if row_change >= 2:
                            priority = max(priority, 300)
                        elif is_isolated and improves_cohesion:
                            # 离群棋子的向前跳跃
                            priority = max(priority, 120)
                        else:
                            # 优先级⑥: 平推前线
                            priority = max(priority, 150)
                    else:
                        # 水平跳跃 - 检查是否有连跳潜力
                        has_chain_potential = False
                        
                        # 检查从跳跃目标位置是否存在后续的跳跃机会
                        if jump_target:
                            # 只检查向前的方向，简化计算
                            forward_directions = []
                            if state.board.turn_color == PlayerColor.RED:
                                forward_directions = [Direction.Down, Direction.DownLeft, Direction.DownRight]
                            else:  # BLUE
                                forward_directions = [Direction.Up, Direction.UpLeft, Direction.UpRight]
                                
                            for next_dir in forward_directions:
                                try:
                                    next_jump_over = jump_target + next_dir
                                    if (0 <= next_jump_over.r < BOARD_N and 
                                        0 <= next_jump_over.c < BOARD_N and
                                        state.board[next_jump_over].state in (PlayerColor.RED, PlayerColor.BLUE)):
                                        
                                        next_jump_target = next_jump_over + next_dir
                                        if (0 <= next_jump_target.r < BOARD_N and 
                                            0 <= next_jump_target.c < BOARD_N and
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
                else:
                    # 非跳跃动作的简化处理
                    if is_forward:
                        # 普通向前移动
                        if is_isolated and improves_cohesion:
                            # 离群棋子移动且提高紧凑度
                            priority = max(priority, 30)
                        else:
                            priority = max(priority, 1)  # 默认最低优先级
                    # 非向前移动保持最低优先级
                    
            elif isinstance(action, GrowAction):
                # 优先级④,⑤,⑦: 造桥补路、阻断对手、防堵自己
                priority = 55  # 中等优先级(在5和6之间)
            
            action_priorities[action] = priority
            legal_actions.append(action)
        
        # 根据优先级排序
        sorted_actions = sorted(legal_actions, key=lambda a: action_priorities[a], reverse=True)
        
        # 取优先级最高的几个动作
        max_actions_to_consider = 12
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
        simulation_count = 8 # Adjusted simulation_count
        for _ in range(simulation_count):
            if current_state.is_terminal(): break
            legal_actions_list = current_state.get_legal_actions()
            if not legal_actions_list: break
            action_to_simulate = random.choice(legal_actions_list)
            try:
                current_state = current_state.move(action_to_simulate)
            except ValueError: 
                break 
        # get_reward() should be from perspective of current_state.board.turn_color
        return current_state.get_reward()

    def backpropagation(self, node, reward_from_sim_leaf_pov):
        # reward_from_sim_leaf_pov is from the perspective of the player whose turn it is AT THE SIMULATION LEAF node (node).
        sim_leaf_player_color = node.state.board.turn_color
        
        # Convert reward to be relative to the root_player_color
        if sim_leaf_player_color == self.root_player_color:
            reward_relative_to_root = reward_from_sim_leaf_pov
        else:
            reward_relative_to_root = -reward_from_sim_leaf_pov
            
        current_node = node
        while current_node:
            if current_node.parent: # current_node is not the root
                # Update visits and total_rewards (which is relative to root_player_color)
                current_node.update(reward_relative_to_root)
            else: # current_node is the root node
                current_node.visits += 1 # Root only updates visits; its total_rewards remains 0.0 as per init.
            current_node = current_node.parent


# Constants for jump directions
ALL_DIRECTIONS_ORDERED = [
    Direction.Up, Direction.Down, Direction.Left, Direction.Right,
    Direction.UpLeft, Direction.UpRight, Direction.DownLeft, Direction.DownRight
]
LEGAL_JUMP_DIRECTIONS_RED = tuple(d for d in ALL_DIRECTIONS_ORDERED if d not in {Direction.Up, Direction.UpRight, Direction.UpLeft})
LEGAL_JUMP_DIRECTIONS_BLUE = tuple(d for d in ALL_DIRECTIONS_ORDERED if d not in {Direction.Down, Direction.DownRight, Direction.DownLeft})

# 新的克隆函数定义
def _clone_board_mcts_version(board_to_clone: Board) -> Board:
    # 使用原始棋盘的当前玩家颜色初始化新棋盘
    new_board = Board(initial_player=board_to_clone.turn_color)

    # 复制棋盘状态 _state
    # 为每个坐标创建新的 CellState 对象
    new_board._state = {
        coord: CellState(cell.state)
        for coord, cell in board_to_clone._state.items()
    }

    # 复制历史记录 _history (浅拷贝列表即可，因为BoardMutation是不可变的)
    new_board._history = list(board_to_clone._history)

    # 复制 MCTS 特有的固定开局步数计数器
    # GameState的__init__方法确保了 board_to_clone 对象上存在这些属性
    new_board._red_fixed_moves = board_to_clone._red_fixed_moves
    new_board._blue_fixed_moves = board_to_clone._blue_fixed_moves
    
    return new_board

class GameState:
    def __init__(self, last_move, board, test_mode=False):
        self.last_move = last_move
        self.board = board
        self.test_mode = test_mode
        if not hasattr(board, "_red_fixed_moves"):
            board._red_fixed_moves = 0
        if not hasattr(board, "_blue_fixed_moves"):
            board._blue_fixed_moves = 0
        self._red_fixed_moves = board._red_fixed_moves
        self._blue_fixed_moves = board._blue_fixed_moves
        self.my_frogs = []
        self._update_my_frogs()

    def _get_bit(self, coord: Coord) -> int:
        if 0 <= coord.r < BOARD_N and 0 <= coord.c < BOARD_N:
            return 1 << (coord.r * BOARD_N + coord.c)
        return 0

    def _get_initial_occupied_bitmask(self) -> int:
        mask = 0
        for r_idx in range(BOARD_N):
            for c_idx in range(BOARD_N):
                coord = Coord(r_idx, c_idx)
                cell_state = self.board[coord].state
                if cell_state == PlayerColor.RED or cell_state == PlayerColor.BLUE:
                    mask |= self._get_bit(coord)
        return mask

    def _is_frog_at(self, coord: Coord, occupied_mask: int) -> bool:
        if not (0 <= coord.r < BOARD_N and 0 <= coord.c < BOARD_N):
            return False
        return bool(occupied_mask & self._get_bit(coord))

    def _is_lilypad_empty_at(self, coord: Coord, occupied_mask: int) -> bool:
        if not (0 <= coord.r < BOARD_N and 0 <= coord.c < BOARD_N):
            return False
        # Check original board for LilyPad, and current mask for emptiness
        return self.board[coord].state == "LilyPad" and not (occupied_mask & self._get_bit(coord))

    def _enumerate_jumps(self, start_coord: Coord, player_color: PlayerColor) -> set[MoveAction]:
        results = set()
        initial_mask = self._get_initial_occupied_bitmask()
        
        stack = [(start_coord, [], initial_mask, {start_coord})]
        
        jump_directions = LEGAL_JUMP_DIRECTIONS_RED if player_color == PlayerColor.RED else LEGAL_JUMP_DIRECTIONS_BLUE

        while stack:
            current_pos, current_path_dirs, current_mask, visited_landings = stack.pop()

            jumped_further_in_this_step = False
            for direction in jump_directions:
                    dr, dc = direction.value.r, direction.value.c # Direction increments
                    
                    # Calculate integer coordinates first
                    r_over, c_over = current_pos.r + dr, current_pos.c + dc
                    r_land, c_land = r_over + dr, c_over + dc

                    # Pre-check bounds for the landing coordinate
                    # If land_coord is out of bounds, skip this direction
                    if not (0 <= r_land < BOARD_N and 0 <= c_land < BOARD_N):
                        continue
                    
                    # If landing coordinates are valid, then over_coord's raw coordinates must also be valid.
                    # Now it's safe to construct Coord objects.
                    over_coord = Coord(r_over, c_over)
                    land_coord = Coord(r_land, c_land)
                    
                    if land_coord in visited_landings:
                        continue
                    
                    if self._is_frog_at(over_coord, current_mask) and \
                       self._is_lilypad_empty_at(land_coord, current_mask):
                        
                        jumped_further_in_this_step = True
                        new_path_dirs = current_path_dirs + [direction]
                        
                        updated_mask = current_mask
                        updated_mask &= ~self._get_bit(current_pos) 
                        updated_mask &= ~self._get_bit(over_coord) 
                        updated_mask |= self._get_bit(land_coord)  
                        
                        new_visited_landings = visited_landings | {land_coord}
                        stack.append((land_coord, new_path_dirs, updated_mask, new_visited_landings))
            
            if not jumped_further_in_this_step and len(current_path_dirs) >= 1:
                results.add(MoveAction(start_coord, tuple(current_path_dirs)))
        return results

    def _update_my_frogs(self):
        self.my_frogs = []
        for r in range(BOARD_N):
            for c in range(BOARD_N):
                coord = Coord(r, c)
                if self.board[coord].state == self.board.turn_color:
                    self.my_frogs.append(coord)

    def is_opening_phase(self):
        return self.board.turn_count < 30
        
    def should_use_fixed_opening(self):
        if self.test_mode:
            return False
        if self.board.turn_count < 15:
            if self.board.turn_color == PlayerColor.RED and self._red_fixed_moves < 5:
                return True
            elif self.board.turn_color == PlayerColor.BLUE and self._blue_fixed_moves < 5:
                return True
        return False
        
    def get_fixed_opening_move(self):
        if self.board.turn_color == PlayerColor.RED:
            if self._red_fixed_moves == 0: return MoveAction(Coord(0, 2), (Direction.Down,))
            elif self._red_fixed_moves == 1: return MoveAction(Coord(0, 5), (Direction.Down,))
            elif self._red_fixed_moves == 2: return GrowAction()
            elif self._red_fixed_moves == 3: return MoveAction(Coord(0,1), (Direction.DownRight,))
            elif self._red_fixed_moves == 4: return MoveAction(Coord(0, 6), (Direction.DownLeft,))
        else:
            if self._blue_fixed_moves == 0: return MoveAction(Coord(7, 2), (Direction.Up,))
            elif self._blue_fixed_moves == 1: return MoveAction(Coord(7, 5), (Direction.Up,))
            elif self._blue_fixed_moves == 2: return GrowAction()
            elif self._blue_fixed_moves == 3: return MoveAction(Coord(7,1), (Direction.UpRight,))
            elif self._blue_fixed_moves == 4: return MoveAction(Coord(7, 6), (Direction.UpLeft,))
        return None

    def get_legal_actions(self) -> list[Action]: # Modified to return a sorted list of Actions
        if self.should_use_fixed_opening() and not self.test_mode:
            fixed_move = self.get_fixed_opening_move()
            if fixed_move is not None: return [fixed_move] # Return as a list
        
        # Use a list of (priority, action) for sorting, then extract actions
        prioritized_actions_tuples = []
        current_player_color = self.board.turn_color

        for coord in self.my_frogs:
            # Generate Sliding Moves
            for direction in ALL_DIRECTIONS_ORDERED:
                slide_action = MoveAction(coord, (direction,))
                try:
                    self.board._validate_move_action(slide_action) 
                    final_slide_coord = coord + direction.value
                    is_forward_slide = False
                    if current_player_color == PlayerColor.RED:
                        if final_slide_coord.r > coord.r: is_forward_slide = True
                    else: 
                        if final_slide_coord.r < coord.r: is_forward_slide = True
                    priority = 55 if is_forward_slide else 1
                    prioritized_actions_tuples.append((priority, slide_action))
                except IllegalActionException:
                    pass 

            # Generate Jump Moves
            jump_actions_for_frog = self._enumerate_jumps(coord, current_player_color)
            for jump_action in jump_actions_for_frog:
                num_segments = len(jump_action.directions)
                current_pos_for_calc = coord 
                final_jump_coord = coord 
                for jump_dir_segment in jump_action.directions:
                    land_coord = current_pos_for_calc + jump_dir_segment.value + jump_dir_segment.value
                    final_jump_coord = land_coord 
                    current_pos_for_calc = land_coord 

                is_forward_jump = False
                if current_player_color == PlayerColor.RED:
                    if final_jump_coord.r > coord.r: is_forward_jump = True
                else: 
                    if final_jump_coord.r < coord.r: is_forward_jump = True
                
                row_change = abs(final_jump_coord.r - coord.r)
                priority = 1 
                if num_segments >= 2:
                    if is_forward_jump and row_change >= 2: priority = 300 
                    elif is_forward_jump: priority = 250 
                    else: priority = 100 
                elif num_segments == 1:
                    if is_forward_jump: priority = 150 
                    else: priority = 20 
                prioritized_actions_tuples.append((priority, jump_action))

        # Generate Grow Action
        current_player_frogs_count = 0
        has_empty_lilypad = False
        for r_idx in range(BOARD_N):
            for c_idx in range(BOARD_N):
                cell_coord = Coord(r_idx, c_idx)
                cell_state_obj = self.board[cell_coord]
                if cell_state_obj.state == current_player_color:
                    current_player_frogs_count += 1
                if cell_state_obj.state == "LilyPad": 
                    has_empty_lilypad = True
        
        if current_player_frogs_count < BOARD_N and has_empty_lilypad:
            prioritized_actions_tuples.append((50, GrowAction())) # Priority for GROW
        
        # Sort actions by priority (descending), then extract the actions themselves
        prioritized_actions_tuples.sort(key=lambda x: x[0], reverse=True)
        
        sorted_actions = [action for priority, action in prioritized_actions_tuples]
        
        return sorted_actions if sorted_actions else [GrowAction()] # Ensure at least GROW if nothing else

    def _check_chain_jump_potential(self, coord): 
        return False # Obsolete, _enumerate_jumps handles this

    def move(self, action):
        new_board = _clone_board_mcts_version(self.board) # 修改此处，使用新的克隆函数
        try:
            new_board.apply_action(action) # ★ 重新添加此行以真正执行动作
            # Store the board state *before* applying the action to help determine slide vs jump
            new_state = GameState(action, new_board, self.test_mode)
            return new_state 
        except IllegalActionException as e:
            raise ValueError(f"Illegal action: {e}") from e

    def is_terminal(self):
        return self.board.game_over

    def get_reward(self):
        if self.is_terminal():
            red_score = self.board._player_score(PlayerColor.RED)
            blue_score = self.board._player_score(PlayerColor.BLUE)
            if self.board.turn_color == PlayerColor.RED:
                return 1.0 if red_score > blue_score else (-1.0 if red_score < blue_score else 0.0)
            else:
                return 1.0 if blue_score > red_score else (-1.0 if blue_score < red_score else 0.0)
        score = 0.0
        red_goal_count = self.board._row_count(PlayerColor.RED, BOARD_N - 1)
        blue_goal_count = self.board._row_count(PlayerColor.BLUE, 0)
        score += 5.0 * (red_goal_count - blue_goal_count)
        return score if self.board.turn_color == PlayerColor.RED else -score

    def _count_jump_opportunities(self, player_color):
        jump_count = 0
        if self.board.turn_color == player_color: # Ensure context is for the player_color
            for frog_coord in self.my_frogs:
                 jumps = self._enumerate_jumps(frog_coord, player_color)
                 for jump_action in jumps:
                     # Corrected: Count number of directions (segments)
                     jump_count += len(jump_action.directions) 
        return jump_count

    def _calculate_cohesion_score(self, player_color, piece_coord):
        cohesion_score = 0
        ally_pieces = []
        for coord_ally, cell_ally in self.board._state.items():
            if cell_ally.state == player_color and coord_ally != piece_coord:
                ally_pieces.append(coord_ally)
        if not ally_pieces: return 0
        total_distance = sum(abs(piece_coord.r - ac.r) + abs(piece_coord.c - ac.c) for ac in ally_pieces)
        avg_distance = total_distance / len(ally_pieces)
        return 1.0 - (avg_distance / (2 * BOARD_N))

    def _check_jump_bridge_formation(self, player_color, target_coord):
        return 0 # Placeholder


if __name__ == '__main__':
    # 创建一个测试场景，尝试执行跳跃动作
    # 使用自带的初始棋盘方法创建棋盘
    basic_board = Board()
    
    # 使用已有棋盘的方法来设置新的棋盘状态
    new_board = Board()
    
    # 清除所有位置
    for r in range(BOARD_N):
        for c in range(BOARD_N):
            coord = Coord(r, c)
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
    
    # 放置红方棋子
    red_cell = None
    for coord, cell in basic_board._state.items():
        if cell.state == PlayerColor.RED:
            red_cell = cell
            break
    
    red_coord = Coord(2, 2)
    if red_cell:
        new_board.set_cell_state(red_coord, red_cell)
    
    # 放置蓝方棋子作为跳跃障碍
    blue_cell = None
    for coord, cell in basic_board._state.items():
        if cell.state == PlayerColor.BLUE:
            blue_cell = cell
            break
            
    blue_coord = Coord(3, 3)
    if blue_cell:
        new_board.set_cell_state(blue_coord, blue_cell)
    
    # 放置目标荷叶
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
    print("=== 测试跳跃功能 ===")
    print("初始棋盘:")
    print(new_board.render())
    
    # 创建GameState并启用测试模式
    state = GameState(None, new_board, test_mode=True)
    legal_actions = state.get_legal_actions()
    print(f"合法动作: {legal_actions}")
    
    # 使用MCTS-Minimax混合算法
    print("\n===== MCTS-Minimax混合算法 =====")
    start_time = time.time()
    mcts = MCTS(state, use_minimax=True, minimax_depth=2, test_mode=True)
    best_action = mcts.search(iterations=30)
    minimax_time = time.time() - start_time
    print(f"耗时: {minimax_time:.2f}秒")
    print(f"最佳动作: {best_action}")
    
    # 对比传统MCTS
    print("\n===== 传统MCTS算法 =====")
    start_time = time.time()
    mcts_traditional = MCTS(state, use_minimax=False, test_mode=True)
    best_action_traditional = mcts_traditional.search(iterations=30)
    traditional_time = time.time() - start_time
    print(f"耗时: {traditional_time:.2f}秒")
    print(f"最佳动作: {best_action_traditional}")

