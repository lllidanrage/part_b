import sys
import os
from copy import deepcopy

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from referee.game import Direction, Coord, Action, MoveAction, GrowAction, IllegalActionException, Board, BOARD_N
from referee.game.player import PlayerColor
from referee.game.board import CellState

# 从agent目录导入MCTS
from agent.MCTS import MCTS, GameState

def create_jump_scenario():
    """
    创建一个必须要跳跃才能通过的局面
    红方在(3,3)位置有一个棋子
    蓝方在(4,3)位置有一个棋子，用于跳跃
    (5,3)位置有一个空荷叶
    """
    board = Board()
    
    # 创建新的状态字典，所有位置初始为空
    new_state = {
        Coord(r, c): CellState(None) 
        for r in range(BOARD_N) 
        for c in range(BOARD_N)
    }
    
    # 放置一个红方棋子在(3,3)
    red_coord = Coord(3, 3)
    new_state[red_coord] = CellState(PlayerColor.RED)
    
    # 放置跳跃用的棋子在(4,3)，使用蓝方棋子
    jump_coord = Coord(4, 3)
    new_state[jump_coord] = CellState(PlayerColor.BLUE)
    
    # 放置一个空荷叶在(5,3)
    lily_coord = Coord(5, 3)
    new_state[lily_coord] = CellState("LilyPad")
    
    # 在另一个位置添加一个普通移动选项（作为对比）
    normal_coord = Coord(3, 5)
    new_state[normal_coord] = CellState(PlayerColor.RED)
    
    normal_target = Coord(4, 5)
    new_state[normal_target] = CellState("LilyPad")
    
    # 更新棋盘状态
    board._state = new_state
    
    # 设置为红方回合
    board.set_turn_color(PlayerColor.RED)
    
    return board

def print_board(board):
    """打印棋盘状态"""
    print("棋盘状态：")
    for r in range(BOARD_N):
        row = ""
        for c in range(BOARD_N):
            coord = Coord(r, c)
            if coord in board._state:
                cell = board._state[coord]
                if cell.state == PlayerColor.RED:
                    row += "R "
                elif cell.state == PlayerColor.BLUE:
                    row += "B "
                elif cell.state == "LilyPad":
                    row += "* "  # 使用*表示空荷叶
                else:
                    row += ". "  # 使用.表示空位置
            else:
                row += ". "
        print(row)

def test_indirect_jump():
    """测试修改后的MCTS是否会优先选择能形成跳跃的动作"""
    # 创建必须跳跃的局面
    board = create_jump_scenario()
    
    print("初始局面：")
    print_board(board)
    
    # 创建游戏状态
    initial_state = GameState(None, board)
    
    # 获取所有合法动作
    legal_actions = initial_state.get_legal_actions()
    print("\n合法动作列表：")
    for action in legal_actions:
        print(action)
    
    # 运行MCTS，增加迭代次数确保有足够的探索
    mcts = MCTS(initial_state)
    best_action = mcts.search(iterations=200)
    
    print("\nMCTS选择的最佳动作:", best_action)
    
    # 检查是否选择了靠近蓝方棋子的移动
    if isinstance(best_action, MoveAction):
        # 计算起始和终点坐标
        init_coord = best_action.coord
        final_coord = init_coord
        for direction in best_action.directions:
            final_coord = final_coord + direction
        
        # 检查移动后的位置是否紧邻蓝方棋子
        is_jump_preparation = False
        for direction in [Direction.Down, Direction.DownLeft, Direction.DownRight, Direction.Left, Direction.Right]:
            try:
                adj_coord = final_coord + direction
                if board[adj_coord].state == PlayerColor.BLUE:
                    # 检查跳过后的位置是否有荷叶
                    jump_target = adj_coord + direction
                    if jump_target.r < BOARD_N and jump_target.c < BOARD_N and board[jump_target].state == "LilyPad":
                        is_jump_preparation = True
                        break
            except (ValueError, IndexError, KeyError):
                continue
        
        if is_jump_preparation:
            print("✓ 成功：MCTS选择了能形成跳跃条件的移动！")
        else:
            print("✗ 失败：MCTS没有选择形成跳跃条件的移动。")
    else:
        print("✗ 失败：MCTS选择了GROW动作而不是移动动作。")
    
    # 如果有红方棋子在(3,3)，检查该棋子是否会移动到靠近蓝方的位置
    red_at_33 = False
    for action in legal_actions:
        if isinstance(action, MoveAction) and action.coord == Coord(3, 3):
            red_at_33 = True
            break
    
    if red_at_33 and best_action.coord == Coord(3, 3):
        print("✓ 成功：MCTS选择了位于(3,3)的红方棋子进行移动，准备跳跃！")
    elif red_at_33:
        print("✗ 失败：有位于(3,3)的红方棋子可以移动，但MCTS选择了其他棋子。")
    
    # 执行最佳动作
    new_state = initial_state.move(best_action)
    print("\n执行动作后的局面：")
    print_board(new_state.board)
    
    # 验证下一步是否可以跳跃
    next_legal_actions = new_state.get_legal_actions()
    has_potential_jump = False
    for action in next_legal_actions:
        if isinstance(action, MoveAction):
            # 检查这个动作是否将移动到下一个红方回合
            init_coord = action.coord
            final_coord = init_coord
            for direction in action.directions:
                next_coord = final_coord + direction
                if next_coord.r < BOARD_N and next_coord.c < BOARD_N and board[next_coord].state in (PlayerColor.RED, PlayerColor.BLUE):
                    # 有可能的跳跃
                    has_potential_jump = True
                    break
    
    if has_potential_jump:
        print("✓ 下一步有可能进行跳跃！")
    else:
        print("✗ 下一步没有可能的跳跃。")

if __name__ == "__main__":
    test_indirect_jump() 