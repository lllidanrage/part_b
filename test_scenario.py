from referee.game import Board, PlayerColor, Coord, Direction, MoveAction
from referee.game.board import CellState
from agent.MCTS import MCTS, GameState

def print_board_and_make_move(state, is_red_turn=True):
    print("初始棋盘:" if state.board.turn_count == 0 else f"{'红' if is_red_turn else '蓝'}方动作后:")
    print(state.board.render())
    print("\n")

def main():
    # 创建初始棋盘
    board = Board()
    
    # 清除所有位置并设置为荷叶
    for r in range(8):
        for c in range(8):
            coord = Coord(r, c)
            board.set_cell_state(coord, CellState("LilyPad"))
    
    # 设置初始棋子
    # 蓝方棋子
    board.set_cell_state(Coord(0, 0), CellState(PlayerColor.BLUE))
    
    # 红方棋子
    board.set_cell_state(Coord(7, 2), CellState(PlayerColor.RED))
    board.set_cell_state(Coord(7, 3), CellState(PlayerColor.RED))
    board.set_cell_state(Coord(7, 4), CellState(PlayerColor.RED))
    board.set_cell_state(Coord(6, 5), CellState(PlayerColor.RED))
    board.set_cell_state(Coord(7, 6), CellState(PlayerColor.RED))
    board.set_cell_state(Coord(7, 7), CellState(PlayerColor.RED))

    # board.set_cell_state(Coord(6, 0), CellState(PlayerColor.RED))
    # board.set_cell_state(Coord(6, 1), CellState(PlayerColor.RED))
    # board.set_cell_state(Coord(6, 3), CellState(PlayerColor.RED))
    # board.set_cell_state(Coord(6, 4), CellState(PlayerColor.RED))
    # board.set_cell_state(Coord(6, 6), CellState(PlayerColor.RED))
    # board.set_cell_state(Coord(6, 7), CellState(PlayerColor.RED))
    
    # 设置为红方回合
    board.set_turn_color(PlayerColor.RED)
    
    # 创建初始状态
    state = GameState(None, board, test_mode=True)
    print_board_and_make_move(state)
    
    # 进行5轮测试
    for i in range(5):
        # 红方行动
        mcts = MCTS(state, use_minimax=True, test_mode=True)
        print("--- Root Children Stats ---")
        best_action = mcts.search(iterations=30)
        print("---------------------------")
        print(f"红方最佳动作: {best_action}")
        state = state.move(best_action)
        print_board_and_make_move(state, True)
        
        if state.is_terminal():
            print("游戏结束!")
            break
            
        # 蓝方固定向右平移
        blue_pos = None
        for r in range(8):
            for c in range(8):
                if state.board[Coord(r, c)].state == PlayerColor.BLUE:
                    blue_pos = Coord(r, c)
                    break
            if blue_pos:
                break
        
        # 如果蓝方棋子到达最右边，则向左移动
        if blue_pos.c == 7:
            blue_action = MoveAction(blue_pos, (Direction.Left,))
        else:
            blue_action = MoveAction(blue_pos, (Direction.Right,))
            
        state = state.move(blue_action)
        print(f"蓝方动作: {blue_action}")
        print_board_and_make_move(state, False)
        
        if state.is_terminal():
            print("游戏结束!")
            break

if __name__ == "__main__":
    main() 