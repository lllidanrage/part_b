import os
import sys
import shutil

def ensure_mcts_in_test_dir():
    """确保MCTS.py文件存在于agent_test目录中"""
    # 获取当前目录和项目根目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    # agent目录中的MCTS.py文件
    agent_mcts_path = os.path.join(project_root, 'agent', 'MCTS.py')
    # 当前目录中的MCTS.py文件
    local_mcts_path = os.path.join(current_dir, 'MCTS.py')
    
    # 检查当前目录是否有MCTS.py文件
    if os.path.exists(local_mcts_path):
        print(f"MCTS.py已存在于{current_dir}目录中")
        return True
    
    # 检查agent目录是否有MCTS.py文件
    if os.path.exists(agent_mcts_path):
        print(f"在agent目录中找到MCTS.py，正在复制到{current_dir}...")
        try:
            shutil.copy2(agent_mcts_path, local_mcts_path)
            print("复制成功！")
            return True
        except Exception as e:
            print(f"复制文件时出错: {str(e)}")
            return False
    
    print("警告：在当前目录和agent目录中都找不到MCTS.py文件！")
    return False

if __name__ == "__main__":
    ensure_mcts_in_test_dir() 