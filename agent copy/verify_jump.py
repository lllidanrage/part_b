import sys
import os
from copy import deepcopy

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print("系统路径:", sys.path)

from referee.game import Direction, Coord, Action, MoveAction, GrowAction, IllegalActionException, Board
from referee.game.player import PlayerColor
from referee.game.board import CellState

def create_simple_board():
    """创建一个简单的场景测试跳跃功能"""
    board = Board()
    
    # 创建新的状态字典，所有位置初始为空
    new_state = {
        Coord(r, c): CellState(None) 
        for r in range(8) 
        for c in range(8)
    }
    
    # 红方起始位置
    red_coord = Coord(1, 1)
    new_state[red_coord] = CellState(PlayerColor.RED)
    
    # 蓝方障碍
    blue_coord = Coord(2, 2)
    new_state[blue_coord] = CellState(PlayerColor.BLUE)
    
    # 目标荷叶
    lily_coord = Coord(3, 3)
    new_state[lily_coord] = CellState("LilyPad")
    
    # 更新棋盘状态
    board._state = new_state
    
    # 设置为红方回合
    board.set_turn_color(PlayerColor.RED)
    
    return board, red_coord, blue_coord, lily_coord

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

def test_simple_jump():
    """测试简单的跳跃动作"""
    board, red_coord, blue_coord, lily_coord = create_simple_board()
    
    print("初始棋盘：")
    print_board(board)
    
    print("\n测试棋盘状态:")
    print(f"1. 红方位置({red_coord})状态: {board[red_coord].state}")
    print(f"2. 蓝方位置({blue_coord})状态: {board[blue_coord].state}")
    print(f"3. 荷叶位置({lily_coord})状态: {board[lily_coord].state}")
    
    # 内部测试中间位置是否被识别为占用
    mid_occupied = board._cell_occupied_by_player(blue_coord)
    print(f"4. 中间位置是否被占用: {mid_occupied}")
    
    # 创建跳跃路径
    direction = Direction.DownRight
    print(f"\n跳跃方向: {direction}")
    
    # 检查路径计算
    first_step = red_coord + direction
    second_step = first_step + direction
    print(f"第一步位置: {first_step}, 应该等于蓝方位置: {blue_coord}")
    print(f"第二步位置: {second_step}, 应该等于荷叶位置: {lily_coord}")
    
    # 测试表示方法1：使用一个方向（普通移动）
    print("\n测试方法1：使用单个方向（普通移动）")
    try:
        action1 = MoveAction(red_coord, (direction,))
        print(f"动作1: {action1}")
        test_board1 = deepcopy(board)
        test_board1.apply_action(action1)
        print("动作1执行成功！")
    except Exception as e:
        print(f"动作1执行失败: {e}")
    
    # 测试表示方法2：使用两个相同方向（标准跳跃表示）
    print("\n测试方法2：使用两个相同方向（标准跳跃表示）")
    try:
        action2 = MoveAction(red_coord, (direction, direction))
        print(f"动作2: {action2}")
        test_board2 = deepcopy(board)
        test_board2.apply_action(action2)
        print("动作2执行成功！")
        print("执行后的棋盘:")
        print_board(test_board2)
    except Exception as e:
        print(f"动作2执行失败: {e}")
    
    # 测试表示方法3：使用直接跳跃（跳两格）
    print("\n测试方法3：使用直接跳跃（跳两格）")
    try:
        # 创建一个直接跳到终点的动作
        action3 = MoveAction(red_coord, (Direction(2, 2),))  # 尝试创建一个可以直接跳2格的方向
        print(f"动作3: {action3}")
        test_board3 = deepcopy(board)
        test_board3.apply_action(action3)
        print("动作3执行成功！")
    except Exception as e:
        print(f"动作3执行失败: {e}")
        
    # 检查Board源代码中关于跳跃的函数
    print("\n检查Board类内部方法:")
    # _is_jump_move, _validate_jump, _resolve_jump_destination等方法
    try:
        test_board = deepcopy(board)
        jump_action = MoveAction(red_coord, (direction, direction))
        
        # 尝试访问内部方法
        print("1. 检查是否为跳跃动作:")
        has_is_jump = hasattr(test_board, '_is_jump_move')
        print(f"   是否有_is_jump_move方法: {has_is_jump}")
        
        if has_is_jump:
            is_jump = test_board._is_jump_move(jump_action)
            print(f"   _is_jump_move结果: {is_jump}")
        
        # 测试更多内部方法
        print("2. 尝试其他内部跳跃相关方法:")
        has_validate_jump = hasattr(test_board, '_validate_jump_move')
        print(f"   是否有_validate_jump_move方法: {has_validate_jump}")
        
        has_resolve_jump = hasattr(test_board, '_resolve_jump_destination')
        print(f"   是否有_resolve_jump_destination方法: {has_resolve_jump}")
    except Exception as e:
        print(f"检查内部方法失败: {e}")
    
    # 测试另一种表示方法：使用更明确的路径
    print("\n测试方法4：使用完整路径表示")
    try:
        # 创建一个明确包含途经点的跳跃路径
        # 从(1,1)经过(2,2)到达(3,3)
        action4 = MoveAction(red_coord, (Direction.DownRight,))
        print(f"动作4(第一步): {action4}")
        
        test_board4 = deepcopy(board)
        # 先移动到中间位置旁边
        try:
            test_board4.apply_action(action4)
            print("第一步移动成功！")
            
            # 尝试第二步移动
            next_coord = blue_coord
            action4_2 = MoveAction(next_coord, (Direction.DownRight,))
            print(f"动作4(第二步): {action4_2}")
            test_board4.apply_action(action4_2)
            print("第二步移动成功！")
        except Exception as e:
            print(f"分步移动失败: {e}")
    except Exception as e:
        print(f"动作4执行失败: {e}")
        
    # 结论
    print("\n结论:")
    print("1. 单次跳跃应使用两个相同方向表示: MoveAction(coord, (direction, direction))")
    print("2. 跳跃动作需要中间有棋子，目标位置是空荷叶")
    print("3. 可能需要分两步实现跳跃: 先移动到中间位置旁边，再从那里移动到目标位置")

if __name__ == "__main__":
    test_simple_jump() 