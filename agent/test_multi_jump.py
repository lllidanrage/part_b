import sys
import os
from copy import deepcopy

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from referee.game import Direction, Coord, Action, MoveAction, GrowAction, IllegalActionException, Board
from referee.game.player import PlayerColor
from referee.game.board import CellState

# 从当前目录或agent目录导入MCTS
try:
    from MCTS import MCTS, GameState
except ImportError:
    from agent.MCTS import MCTS, GameState

def create_multi_jump_scenario():
    """
    创建一个必须要多次跳跃才能获得最大利益的局面
    红方在(1,3)位置有一个棋子
    蓝方在(2,3)和(4,3)位置各有一个棋子
    (3,3)和(5,3)位置有空荷叶
    红方可以连续跳过两个蓝方棋子到达(5,3)
    """
    board = Board()
    
    # 创建新的状态字典，所有位置初始为空
    new_state = {
        Coord(r, c): CellState(None) 
        for r in range(8) 
        for c in range(8)
    }
    
    # 红方起始位置
    red_coord = Coord(1, 3)
    new_state[red_coord] = CellState(PlayerColor.RED)
    
    # 蓝方障碍1
    blue_coord1 = Coord(2, 3)
    new_state[blue_coord1] = CellState(PlayerColor.BLUE)
    
    # 中间荷叶
    lily_coord1 = Coord(3, 3)
    new_state[lily_coord1] = CellState("LilyPad")
    
    # 蓝方障碍2
    blue_coord2 = Coord(4, 3)
    new_state[blue_coord2] = CellState(PlayerColor.BLUE)
    
    # 目标荷叶
    lily_coord2 = Coord(5, 3)
    new_state[lily_coord2] = CellState("LilyPad")
    
    # 添加一个单步跳跃的选项（作为对比）
    red_coord2 = Coord(1, 5)
    new_state[red_coord2] = CellState(PlayerColor.RED)
    
    blue_coord3 = Coord(2, 5)
    new_state[blue_coord3] = CellState(PlayerColor.BLUE)
    
    lily_coord3 = Coord(3, 5)
    new_state[lily_coord3] = CellState("LilyPad")
    
    # 更新棋盘状态
    board._state = new_state
    
    # 设置为红方回合
    board.set_turn_color(PlayerColor.RED)
    
    return board

def print_board(board):
    """打印棋盘状态"""
    print("棋盘状态：")
    for r in range(8):
        row = ""
        for c in range(8):
            coord = Coord(r, c)
            if coord in board._state:
                cell = board._state[coord]
                if cell.state == PlayerColor.RED:
                    row += "R "
                elif cell.state == PlayerColor.BLUE:
                    row += "B "
                elif cell.state == "LilyPad":
                    row += "* "  # 使用*表示空荷叶，而不是L
                else:
                    row += ". "  # 使用.表示空位置
            else:
                row += ". "
        print(row)

def test_multi_jump_action():
    """测试MCTS是否会选择多次跳跃动作"""
    # 创建多次跳跃的局面
    board = create_multi_jump_scenario()
    
    print("初始局面：")
    print_board(board)
    
    # 创建游戏状态
    initial_state = GameState(None, board)
    
    # 获取所有合法动作
    legal_actions = initial_state.get_legal_actions()
    print("\n合法动作列表：")
    for action in legal_actions:
        print(action)
    
    # 运行MCTS
    mcts = MCTS(initial_state)
    best_action = mcts.search(iterations=100)
    
    print("\nMCTS选择的最佳动作:", best_action)
    
    # 检查是否是多次跳跃动作
    if isinstance(best_action, MoveAction):
        if len(best_action.directions) > 1:
            print(f"MCTS成功选择了多次跳跃动作! 跳跃次数: {len(best_action.directions)}")
            print(f"跳跃方向: {best_action.directions}")
        elif len(best_action.directions) == 1:
            print("MCTS选择了单次跳跃或普通移动。")
            print(f"移动方向: {best_action.directions[0]}")
        else:
            print("MCTS选择了未知类型的移动动作。")
    else:
        print("MCTS选择了GROW动作，而不是跳跃动作。")
    
    # 执行最佳动作
    new_state = initial_state.move(best_action)
    print("\n执行动作后的局面：")
    print_board(new_state.board)

if __name__ == "__main__":
    test_multi_jump_action() 