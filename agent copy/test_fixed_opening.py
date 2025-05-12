#!/usr/bin/env python3
import sys
import os
from copy import deepcopy

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from referee.game import Direction, MoveAction, GrowAction, IllegalActionException, BOARD_N, Board, Coord
from referee.game.player import PlayerColor
from MCTS import MCTS, GameState

def test_fixed_opening():
    """测试固定开局策略"""
    print("=== 测试固定开局策略 ===")
    
    # 创建一个标准初始棋盘
    board = Board()
    state = GameState(None, board)
    
    # 模拟前3步红方行动
    print("\n红方固定开局：")
    for i in range(3):
        # 显示当前固定开局计数
        print(f"当前固定开局计数: 红方={state._red_fixed_moves}, 蓝方={state._blue_fixed_moves}")
        
        # 使用MCTS选择动作
        mcts = MCTS(state, use_minimax=True, minimax_depth=1)
        action = mcts.search(iterations=10)
        
        print(f"步骤 {i+1}: {action}")
        
        # 执行动作
        state = state.move(action)
        print(board.render())
        
        # 如果不是最后一步，执行蓝方的随机行动
        if i < 2:
            # 获取蓝方的合法行动
            legal_actions = list(state.get_legal_actions())
            if legal_actions:
                # 随机选择一个行动
                blue_action = legal_actions[0]
                print(f"蓝方行动: {blue_action}")
                state = state.move(blue_action)
    
    # 显示最终计数
    print(f"最终固定开局计数: 红方={state._red_fixed_moves}, 蓝方={state._blue_fixed_moves}")
    
    # 创建一个新的棋盘，测试蓝方固定开局
    board = Board()
    # 先由红方执行一次随机动作
    state = GameState(None, board)
    legal_actions = list(state.get_legal_actions())
    if legal_actions:
        red_action = legal_actions[0]
        print(f"\n红方行动: {red_action}")
        state = state.move(red_action)
    
    # 模拟前3步蓝方行动
    print("\n蓝方固定开局：")
    for i in range(3):
        # 显示当前固定开局计数
        print(f"当前固定开局计数: 红方={state._red_fixed_moves}, 蓝方={state._blue_fixed_moves}")
        
        # 使用MCTS选择动作
        mcts = MCTS(state, use_minimax=True, minimax_depth=1)
        action = mcts.search(iterations=10)
        
        print(f"步骤 {i+1}: {action}")
        
        # 执行动作
        state = state.move(action)
        print(board.render())
        
        # 如果不是最后一步，执行红方的随机行动
        if i < 2:
            # 获取红方的合法行动
            legal_actions = list(state.get_legal_actions())
            if legal_actions:
                # 随机选择一个行动
                red_action = legal_actions[0]
                print(f"红方行动: {red_action}")
                state = state.move(red_action)
    
    # 显示最终计数
    print(f"最终固定开局计数: 红方={state._red_fixed_moves}, 蓝方={state._blue_fixed_moves}")

if __name__ == "__main__":
    test_fixed_opening() 