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

def create_jump_scenario():
    """创建一个简单的场景测试跳跃机制"""
    board = Board()
    
    # 创建新的状态字典，所有位置初始为空
    new_state = {
        Coord(r, c): CellState(None) 
        for r in range(8) 
        for c in range(8)
    }
    
    # 放置红方棋子
    red_coord = Coord(3, 3)
    new_state[red_coord] = CellState(PlayerColor.RED)
    
    # 放置蓝方棋子作为跳跃障碍
    jump_coord = Coord(4, 3)
    new_state[jump_coord] = CellState(PlayerColor.BLUE)
    
    # 放置目标荷叶
    target_coord = Coord(5, 3)
    new_state[target_coord] = CellState("LilyPad")
    
    # 更新棋盘状态
    board._state = new_state
    
    # 设置为红方回合
    board.set_turn_color(PlayerColor.RED)
    
    return board, red_coord, jump_coord, target_coord

def create_fixed_jump_scenario():
    """创建一个确认能跳跃的场景"""
    board = Board()
    
    # 创建新的状态字典，所有位置初始为空
    new_state = {
        Coord(r, c): CellState(None) 
        for r in range(8) 
        for c in range(8)
    }
    
    # 放置红方起始位置
    start_coord = Coord(1, 1)
    new_state[start_coord] = CellState(PlayerColor.RED)
    
    # 第一个跳跃障碍
    jump1_coord = Coord(2, 2)
    new_state[jump1_coord] = CellState(PlayerColor.BLUE)
    
    # 第一个降落点
    landing1_coord = Coord(3, 3)
    new_state[landing1_coord] = CellState("LilyPad")
    
    # 第二个跳跃障碍
    jump2_coord = Coord(4, 4)
    new_state[jump2_coord] = CellState(PlayerColor.BLUE)
    
    # 第二个降落点（最终目标）
    landing2_coord = Coord(5, 5)
    new_state[landing2_coord] = CellState("LilyPad")
    
    # 更新棋盘状态
    board._state = new_state
    
    # 设置为红方回合
    board.set_turn_color(PlayerColor.RED)
    
    return board, start_coord, landing2_coord

def test_jump_formats():
    """测试各种跳跃动作格式"""
    board, red_coord, jump_coord, target_coord = create_jump_scenario()
    
    print("===== 测试跳跃动作格式 =====")
    print("初始棋盘：")
    print_board(board)
    
    # 尝试单次正常移动（应成功）
    normal_move = MoveAction(red_coord, (Direction.Down,))
    print("\n尝试单次正常移动:", normal_move)
    try:
        new_board = deepcopy(board)
        new_board.apply_action(normal_move)
        print("单次移动成功！")
        print("移动后的棋盘:")
        print_board(new_board)
    except Exception as e:
        print("单次移动失败:", e)
    
    # 手动检查中间位置是否有棋子
    print("\n===== 检查跳跃条件 =====")
    print(f"起始位置 {red_coord} 状态: {board[red_coord].state}")
    print(f"中间位置 {jump_coord} 状态: {board[jump_coord].state}")
    print(f"目标位置 {target_coord} 状态: {board[target_coord].state}")
    print(f"中间位置是否被玩家占用: {board._cell_occupied_by_player(jump_coord)}")
    
    # 尝试创建跳跃动作（用两个方向表示）
    print("\n===== 尝试单方向跳跃 =====")
    jump_action = MoveAction(red_coord, (Direction.Down, Direction.Down))
    print("跳跃动作:", jump_action)
    print("方向列表长度:", len(jump_action.directions))
    
    try:
        new_board = deepcopy(board)
        print("尝试应用跳跃动作...")
        new_board.apply_action(jump_action)
        print("跳跃成功!")
        print("跳跃后的棋盘:")
        print_board(new_board)
    except Exception as e:
        print("跳跃失败:", e)

def test_multi_jump():
    """测试多次连续跳跃"""
    board, start_coord, final_coord = create_fixed_jump_scenario()
    
    print("\n===== 测试多次连续跳跃 =====")
    print("初始棋盘：")
    print_board(board)
    
    print(f"\n从 {start_coord} 到 {final_coord}")
    
    # 尝试单次对角线跳跃（应该成功）
    single_jump = MoveAction(start_coord, (Direction.DownRight,))
    print("\n尝试单次对角线移动:", single_jump)
    try:
        new_board = deepcopy(board)
        mutation = new_board.apply_action(single_jump)
        print("单次移动成功！")
    except Exception as e:
        print("单次移动失败:", e)
    
    # 尝试多次连续跳跃
    multi_jump = MoveAction(start_coord, (Direction.DownRight, Direction.DownRight, Direction.DownRight, Direction.DownRight))
    print("\n尝试多次连续跳跃:", multi_jump)
    try:
        new_board = deepcopy(board)
        mutation = new_board.apply_action(multi_jump)
        print("多次连续跳跃成功！最终状态:")
        print_board(new_board)
    except Exception as e:
        print("多次连续跳跃失败:", e)
        
        # 尝试其他格式
        print("\n尝试其他格式...")
        
        # 尝试一次跳一格的格式
        jump1 = MoveAction(start_coord, (Direction.DownRight, Direction.DownRight))
        print("\n尝试第一次跳跃:", jump1)
        try:
            board1 = deepcopy(board)
            board1.apply_action(jump1)
            print("第一次跳跃成功！")
            
            # 从新位置继续跳跃
            landing1 = Coord(3, 3)
            jump2 = MoveAction(landing1, (Direction.DownRight, Direction.DownRight))
            print("尝试第二次跳跃:", jump2)
            board1.apply_action(jump2)
            print("第二次跳跃也成功！最终状态:")
            print_board(board1)
        except Exception as e:
            print("分段跳跃失败:", e)
    
    # 打印结论
    print("\n===== 结论 =====")
    print("1. 对于普通移动，使用 MoveAction(coord, (direction,))")
    print("2. 对于单次跳跃，使用 MoveAction(coord, (direction, direction))")
    print("3. 对于多次跳跃，需要使用多个单独的MoveAction，每次一个跳跃")

if __name__ == "__main__":
    test_jump_formats()
    test_multi_jump() 