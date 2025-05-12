import sys
import os
from copy import deepcopy

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from referee.game import Direction, Coord, MoveAction, GrowAction, Board, BOARD_N, IllegalActionException
from referee.game.player import PlayerColor
from referee.game.board import CellState

# 创建一个直接跳跃的测试场景
def create_jump_board():
    board = Board()
    
    # 创建新的状态字典，所有位置初始为空
    new_state = {
        Coord(r, c): CellState(None) 
        for r in range(BOARD_N) 
        for c in range(BOARD_N)
    }
    
    # 放置一个红方棋子在(2,3)
    red_coord = Coord(2, 3)
    new_state[red_coord] = CellState(PlayerColor.RED)
    
    # 放置跳跃用的棋子在(3,3)，使用蓝方棋子
    jump_coord = Coord(3, 3)
    new_state[jump_coord] = CellState(PlayerColor.BLUE)
    
    # 放置一个空荷叶在(4,3)
    lily_coord = Coord(4, 3)
    new_state[lily_coord] = CellState("LilyPad")
    
    # 更新棋盘状态
    board._state = new_state
    
    # 设置为红方回合
    board.set_turn_color(PlayerColor.RED)
    
    return board

# 打印棋盘状态
def print_board(board):
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
                    row += "* "
                else:
                    row += ". "
            else:
                row += ". "
        print(row)

# 测试直接跳跃动作
def test_direct_jump():
    # 创建测试棋盘
    board = create_jump_board()
    print("测试棋盘初始状态:")
    print_board(board)
    
    # 创建跳跃动作 - 使用单方向表示跳跃
    red_coord = Coord(2, 3)
    
    # 测试双方向跳跃动作 (旧方式 - 不正确的方式)
    jump_action = MoveAction(red_coord, (Direction.Down, Direction.Down))
    print(f"\n尝试执行双方向跳跃动作: {jump_action}")
    try:
        board.apply_action(jump_action)
        print("✓ 意外: 双方向跳跃动作执行成功!")
    except IllegalActionException as e:
        print(f"✗ 预期: 双方向跳跃动作失败，错误: {e}")
        
    # 重新创建棋盘
    board = create_jump_board()
    
    # 测试单方向跳跃动作 (正确的方式 - 这是我们应该使用的)
    jump_action = MoveAction(red_coord, (Direction.Down,))
    print(f"\n尝试执行单方向跳跃动作: {jump_action}")
    
    try:
        # 执行跳跃动作
        board.apply_action(jump_action)
        print("✓ 成功: 单方向跳跃动作执行成功!")
        
        # 打印执行后的棋盘
        print("\n执行跳跃后的棋盘:")
        print_board(board)
        
        # 验证红方棋子是否正确移动到了荷叶位置
        lily_coord = Coord(4, 3)
        if board[lily_coord].state == PlayerColor.RED:
            print("✓ 成功: 红方棋子成功跳到了荷叶位置")
        else:
            print(f"✗ 失败: 红方棋子没有到达荷叶位置，该位置状态为 {board[lily_coord].state}")
            
    except IllegalActionException as e:
        print(f"✗ 失败: 无法执行单方向跳跃动作，错误: {e}")
        print(f"错误类型: {type(e)}")
        print(f"错误详情: {str(e)}")

# 测试Board实现中对于普通移动的处理
def test_normal_move():
    # 创建棋盘
    board = create_jump_board()
    print("\n测试普通移动:")
    
    # 创建普通移动，尝试移动到有棋子的位置
    red_coord = Coord(2, 3)
    move_action = MoveAction(red_coord, (Direction.Down,))
    
    try:
        # 该移动应该被特殊处理为跳跃，因为目标位置有蓝方棋子
        print(f"尝试移动到有棋子的位置: {move_action}")
        board.apply_action(move_action)
        print("✓ 成功: 移动自动处理为跳跃")
        
        # 检查是否正确跳到了荷叶位置
        lily_coord = Coord(4, 3)
        if board[lily_coord].state == PlayerColor.RED:
            print("✓ 成功: 红方棋子被自动跳到了荷叶位置")
        else:
            print(f"✗ 失败: 红方棋子没有到达荷叶位置")
    except IllegalActionException as e:
        print(f"✗ 失败: 无法执行移动，错误: {e}")
    
    # 创建合法的普通移动，移动到侧面
    # 重新创建棋盘
    board = create_jump_board()
    
    # 修改棋盘，在右侧放置一个荷叶
    right_coord = Coord(2, 4)
    board._state[right_coord] = CellState("LilyPad")
    
    move_action = MoveAction(red_coord, (Direction.Right,))
    
    try:
        print(f"\n尝试普通移动到侧面荷叶: {move_action}")
        board.apply_action(move_action)
        print("✓ 成功: 普通移动执行成功")
        print("移动后的棋盘:")
        print_board(board)
    except IllegalActionException as e:
        print(f"✗ 失败: 无法执行普通移动，错误: {e}")

if __name__ == "__main__":
    print("=== 测试直接跳跃 ===")
    test_direct_jump()
    
    print("\n=== 测试普通移动 ===")
    test_normal_move() 