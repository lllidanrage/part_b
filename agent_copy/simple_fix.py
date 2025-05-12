import sys
import os
from copy import deepcopy

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from referee.game import Direction, Coord, MoveAction, GrowAction, Board, BOARD_N
from referee.game.player import PlayerColor
from referee.game.board import CellState

# 创建一个简单的测试场景
def create_test_board():
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

# 获取最佳移动
def get_best_move(board):
    # 检查红方棋子位置
    red_coord = None
    blue_coord = None
    lily_coord = None
    
    for r in range(BOARD_N):
        for c in range(BOARD_N):
            coord = Coord(r, c)
            if coord in board._state:
                cell = board._state[coord]
                if cell.state == PlayerColor.RED and r == 3 and c == 3:
                    red_coord = coord
                elif cell.state == PlayerColor.BLUE and r == 4 and c == 3:
                    blue_coord = coord
                elif cell.state == "LilyPad" and r == 5 and c == 3:
                    lily_coord = coord
    
    if red_coord and blue_coord and lily_coord:
        # 找到所有可能的移动方向
        all_directions = [Direction.Down, Direction.DownLeft, Direction.DownRight, Direction.Left, Direction.Right]
        
        # 检查哪个方向使红方棋子靠近蓝方棋子
        best_dir = None
        best_score = -1
        
        for dir in all_directions:
            try:
                new_coord = red_coord + dir
                if new_coord.r >= 0 and new_coord.r < BOARD_N and new_coord.c >= 0 and new_coord.c < BOARD_N:
                    # 计算与蓝方棋子的距离
                    distance = abs(new_coord.r - blue_coord.r) + abs(new_coord.c - blue_coord.c)
                    
                    # 如果直接相邻蓝方棋子，这是最佳选择
                    if distance == 1:
                        return MoveAction(red_coord, (dir,))
                    
                    # 记录最佳方向（使距离最小）
                    if best_score == -1 or distance < best_score:
                        best_score = distance
                        best_dir = dir
            except Exception:
                continue
        
        # 如果找到了最佳方向，返回移动动作
        if best_dir:
            return MoveAction(red_coord, (best_dir,))
    
    # 如果无法确定最佳移动，返回GROW动作
    return GrowAction()

# 主测试函数
def main():
    # 创建测试棋盘
    board = create_test_board()
    print("测试棋盘初始状态:")
    print_board(board)
    
    # 获取最佳移动
    best_move = get_best_move(board)
    print(f"\n选择的最佳动作: {best_move}")
    
    # 分析这个动作
    if isinstance(best_move, MoveAction):
        init_coord = best_move.coord
        direction = best_move.directions[0]
        new_coord = init_coord + direction
        
        print(f"从 ({init_coord.r},{init_coord.c}) 移动到 ({new_coord.r},{new_coord.c})")
        
        # 检查是否靠近蓝方棋子
        for r in range(BOARD_N):
            for c in range(BOARD_N):
                coord = Coord(r, c)
                if coord in board._state and board._state[coord].state == PlayerColor.BLUE:
                    distance = abs(new_coord.r - r) + abs(new_coord.c - c)
                    if distance == 1:
                        print("✓ 成功: 移动后与蓝方棋子相邻，准备跳跃!")
    else:
        print("✗ 失败: 没有选择移动动作")

if __name__ == "__main__":
    main() 