import sys
import os
from copy import deepcopy

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print("系统路径:", sys.path)

from referee.game import Direction, Coord, Action, MoveAction, GrowAction, IllegalActionException, Board
from referee.game.player import PlayerColor
from referee.game.board import CellState

# 从当前目录或agent目录导入MCTS
try:
    print("尝试从当前目录导入MCTS")
    from MCTS import MCTS, GameState
    print("从当前目录导入MCTS成功")
except ImportError as e:
    print("从当前目录导入失败:", e)
    try:
        print("尝试从agent目录导入MCTS")
        from agent.MCTS import MCTS, GameState
        print("从agent目录导入MCTS成功")
    except ImportError as e:
        print("从agent目录导入也失败:", e)
        raise

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
        for r in range(8) 
        for c in range(8)
    }
    
    # 放置一个红方棋子在(3,3)
    red_coord = Coord(3, 3)
    new_state[red_coord] = CellState(PlayerColor.RED)
    
    # 放置跳跃用的棋子在(4,3)，使用蓝方棋子
    jump_coord = Coord(4, 3)
    new_state[jump_coord] = CellState(PlayerColor.BLUE)  # 改为蓝方棋子
    
    # 放置一个空荷叶在(5,3)
    lily_coord = Coord(5, 3)
    new_state[lily_coord] = CellState("LilyPad")
    
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

def test_jump_action():
    """测试MCTS是否会选择跳跃动作"""
    # 创建必须跳跃的局面
    board = create_jump_scenario()
    
    print("初始局面：")
    print_board(board)
    
    # 创建游戏状态
    initial_state = GameState(None, board, test_mode=True)
    
    # 手动检查是否可能有跳跃动作
    print("\n检查跳跃动作可能性：")
    red_coord = Coord(3, 3)
    blue_coord = Coord(4, 3)
    lily_coord = Coord(5, 3)
    
    print(f"红方位置: {red_coord}")
    print(f"蓝方位置: {blue_coord}")
    print(f"荷叶位置: {lily_coord}")
    
    # 添加更详细的验证
    print("\n详细检查棋盘状态:")
    print(f"1. 红方位置状态: {board[red_coord].state}, 期望值: {PlayerColor.RED}")
    print(f"2. 蓝方位置状态: {board[blue_coord].state}, 期望值: {PlayerColor.BLUE}")
    print(f"3. 荷叶位置状态: {board[lily_coord].state}, 期望值: 'LilyPad'")
    
    # 检查中间位置是否被占用
    mid_occupied = board._cell_occupied_by_player(blue_coord)
    print(f"4. 中间位置被占用: {mid_occupied}, 应该是True")
    
    # 检查方向和跳跃位置计算
    print("\n检查跳跃路径计算:")
    direction = Direction.Down
    print(f"跳跃方向: {direction}")
    first_step = red_coord + direction
    print(f"第一步位置: {first_step}, 实际值: {blue_coord}")
    second_step = first_step + direction
    print(f"第二步位置: {second_step}, 实际值: {lily_coord}")
    
    if board[red_coord].state == PlayerColor.RED and board[blue_coord].state == PlayerColor.BLUE and board[lily_coord].state == "LilyPad":
        print("\n场景设置正确，应该可以进行跳跃")
        
        # 尝试手动创建跳跃动作
        jump_action = MoveAction(red_coord, (Direction.Down, Direction.Down))
        print(f"手动创建的跳跃动作: {jump_action}")
        print(f"跳跃方向数量: {len(jump_action.directions)}")
        print(f"跳跃方向列表: {jump_action.directions}")
        
        # 测试这个动作是否合法
        try:
            new_board = deepcopy(board)
            print("尝试应用跳跃动作...")
            mutation = new_board.apply_action(jump_action)
            print("跳跃动作可以成功应用!")
        except Exception as e:
            print(f"跳跃动作无法应用: {e}")
            print(f"异常类型: {type(e)}")
    else:
        print("场景设置不正确，无法进行跳跃")
        print(f"红方位置状态: {board[red_coord].state}")
        print(f"蓝方位置状态: {board[blue_coord].state}")
        print(f"荷叶位置状态: {board[lily_coord].state}")
    
    # 获取所有合法动作
    legal_actions = initial_state.get_legal_actions()
    print("\n合法动作列表：")
    for action in legal_actions:
        print(action)
    
    # 运行MCTS
    mcts = MCTS(initial_state, test_mode=True)
    best_action = mcts.search(iterations=50)
    
    print("\nMCTS选择的最佳动作:", best_action)
    
    # 检查是否是跳跃动作
    if isinstance(best_action, MoveAction):
        if len(best_action.directions) > 1 or best_action.directions[0] in [Direction.Down, Direction.DownLeft, Direction.DownRight]:
            print("MCTS成功选择了跳跃动作!")
        else:
            print("MCTS没有选择跳跃动作，而是选择了普通移动。")
    else:
        print("MCTS选择了GROW动作，而不是跳跃动作。")
    
    # 执行最佳动作
    new_state = initial_state.move(best_action)
    print("\n执行动作后的局面：")
    print_board(new_state.board)

if __name__ == "__main__":
    test_jump_action() 