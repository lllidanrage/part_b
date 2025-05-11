import sys
import os
from copy import deepcopy

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from referee.game import Direction, Coord, Action, MoveAction, GrowAction, IllegalActionException, Board
from referee.game.player import PlayerColor
from referee.game.board import CellState

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
                    row += "* "  # 使用*表示空荷叶
                else:
                    row += ". "
            else:
                row += ". "
        print(row)

def create_jump_board2():
    """创建一个可以测试跳跃的棋盘"""
    board = Board()
    
    # 创建新的状态字典，所有位置初始为空
    new_state = {
        Coord(r, c): CellState(None) 
        for r in range(8) 
        for c in range(8)
    }
    
    # 放置红方棋子
    red_coord = Coord(2, 2)
    new_state[red_coord] = CellState(PlayerColor.RED)
    
    # 放置可跳过的棋子
    jump_coord = Coord(3, 3)
    new_state[jump_coord] = CellState(PlayerColor.BLUE)  # 使用蓝方棋子
    
    # 放置目标荷叶
    lily_coord = Coord(4, 4)
    new_state[lily_coord] = CellState("LilyPad")
    
    # 更新棋盘状态
    board._state = new_state
    
    # 设置为红方回合
    board.set_turn_color(PlayerColor.RED)
    
    return board, red_coord, jump_coord, lily_coord

def test_diagonal_jump():
    """测试对角线跳跃"""
    board, red_coord, jump_coord, lily_coord = create_jump_board2()
    
    print("初始棋盘：")
    print_board(board)
    
    print(f"\n红方位置: {red_coord}")
    print(f"跳跃位置: {jump_coord}")
    print(f"目标荷叶: {lily_coord}")
    
    # 尝试对角线跳跃动作 - 使用DownRight方向
    jump_action = MoveAction(red_coord, (Direction.DownRight, Direction.DownRight))
    print(f"\n尝试对角线跳跃动作: {jump_action}")
    
    try:
        new_board = deepcopy(board)
        mutation = new_board.apply_action(jump_action)
        print("\n跳跃成功!")
        print("跳跃后的棋盘:")
        print_board(new_board)
        return True
    except IllegalActionException as e:
        print(f"\n跳跃失败: {e}")
        return False

if __name__ == "__main__":
    test_diagonal_jump() 