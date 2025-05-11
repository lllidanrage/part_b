#!/usr/bin/env python
# MCTS 性能测试脚本

import argparse
import random
import time
from referee.game.board import Board
from referee.game.player import PlayerColor
from agent.MCTS import MCTS, GameState

def setup_parser():
    """配置命令行参数解析器"""
    parser = argparse.ArgumentParser(description='MCTS性能基准测试')
    parser.add_argument('--iters', type=int, default=200, help='MCTS搜索的迭代次数')
    parser.add_argument('--runs', type=int, default=5, help='重复运行的次数')
    parser.add_argument('--seed', type=int, default=42, help='随机数种子')
    return parser

def create_game_state(turns=0):
    """创建一个游戏状态，可以是初始状态或者前进几个回合的状态"""
    board = Board()  # 创建初始棋盘
    state = GameState(None, board)
    
    # 如果需要前进几个回合
    if turns > 0:
        # 这里可以添加代码，让游戏前进指定的回合数
        pass
        
    return state

def main():
    """主函数：执行基准测试"""
    args = setup_parser().parse_args()
    
    # 设置随机数种子
    random.seed(args.seed)
    
    print(f"开始MCTS基准测试 - 迭代次数: {args.iters}, 运行次数: {args.runs}")
    
    # 记录总耗时
    total_time = 0
    
    # 多次运行以获取平均性能
    for run in range(args.runs):
        print(f"运行 {run+1}/{args.runs}...")
        
        # 每次运行都创建一个新的游戏状态
        state = create_game_state()
        
        # 创建MCTS实例
        mcts = MCTS(state)
        
        try:
            # 计时
            start_time = time.time()
            
            # 执行MCTS搜索
            best_action = mcts.search(iterations=args.iters)
            
            # 记录耗时
            elapsed = time.time() - start_time
            total_time += elapsed
            
            print(f"  运行耗时: {elapsed:.4f}秒")
            print(f"  最佳动作: {best_action}")
        except Exception as e:
            print(f"  运行出错: {e}")
            # 可以选择继续或中断
            continue
    
    # 输出平均性能
    avg_time = total_time / args.runs
    print(f"\n平均每次运行耗时: {avg_time:.4f}秒")
    print(f"每次迭代平均耗时: {avg_time * 1000 / args.iters:.4f}毫秒")

if __name__ == "__main__":
    main() 