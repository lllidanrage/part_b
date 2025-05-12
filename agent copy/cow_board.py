from referee.game.board import Board, CellState, BoardMutation
from referee.game.coord import Coord
from referee.game.player import PlayerColor
from referee.game.actions import Action, MoveAction, GrowAction
from referee.game.exceptions import IllegalActionException
from referee.game.constants import BOARD_N, MAX_TURNS

class CoWBoard:
    """
    写时复制棋盘类。
    保持对父棋盘的引用，只存储被修改的格子状态。
    只有在需要时才创建完整的副本，大大减少内存使用和复制开销。
    """
    def __init__(self, board=None, parent=None):
        """
        初始化一个写时复制棋盘。
        
        Args:
            board: 标准 Board 对象，如果提供则从中初始化
            parent: 父 CoWBoard 对象，如果提供则共享其状态
        """
        # 支持固定开局所需的属性
        self._red_fixed_moves = 0
        self._blue_fixed_moves = 0
        
        if board is not None:
            # 从标准 Board 实例创建
            self._board = board
            self._parent = None
            self._modified_cells = {}  # 没有修改，空字典
            
            # 如果原始棋盘有固定开局计数，则复制
            if hasattr(board, "_red_fixed_moves"):
                self._red_fixed_moves = board._red_fixed_moves
            if hasattr(board, "_blue_fixed_moves"):
                self._blue_fixed_moves = board._blue_fixed_moves
                
        elif parent is not None:
            # 从父 CoWBoard 创建
            self._board = parent._board  # 引用同一个底层棋盘
            self._parent = parent
            self._modified_cells = {}  # 初始没有修改
            
            # 复制父棋盘的固定开局计数
            self._red_fixed_moves = parent._red_fixed_moves
            self._blue_fixed_moves = parent._blue_fixed_moves
            
        else:
            # 创建新的棋盘
            self._board = Board()
            self._parent = None
            self._modified_cells = {}
    
    def __getitem__(self, coord):
        """获取指定坐标的格子状态，考虑修改过的格子"""
        # 首先检查当前实例中是否有修改
        if coord in self._modified_cells:
            return self._modified_cells[coord]
        
        # 如果没有修改，递归检查父链
        current = self._parent
        while current:
            if coord in current._modified_cells:
                return current._modified_cells[coord]
            current = current._parent
        
        # 如果整个链上都没找到修改，返回底层棋盘的状态
        return self._board[coord]
    
    def clone(self):
        """高效克隆，创建指向同一底层棋盘的新 CoWBoard"""
        return CoWBoard(parent=self)
    
    def apply_action(self, action):
        """应用动作并记录修改的格子"""
        # 首先在底层棋盘上模拟操作，以获取将更改的单元格
        # 由于我们需要底层棋盘对象的验证逻辑，这里使用临时克隆
        temp_board = self._board.clone()
        mutation = temp_board.apply_action(action)
        
        # 记录修改的格子
        for cell_mutation in mutation.cell_mutations:
            self._modified_cells[cell_mutation.cell] = cell_mutation.next
        
        # 更新回合颜色
        self._turn_color = temp_board.turn_color
        
        # 更新固定开局计数
        if self._turn_color == PlayerColor.BLUE:  # 刚刚是红方行动
            self._red_fixed_moves += 1
        else:  # 刚刚是蓝方行动
            self._blue_fixed_moves += 1
        
        return mutation
    
    @property
    def turn_color(self):
        """当前回合玩家颜色"""
        if hasattr(self, '_turn_color'):
            return self._turn_color
        return self._board.turn_color
    
    @property
    def turn_count(self):
        """已进行的回合数"""
        return self._board.turn_count + len(self._get_all_mutations()) // 2  # 每个动作影响约2个格子
    
    @property
    def game_over(self):
        """游戏是否结束"""
        if self.turn_limit_reached:
            return True
            
        # 检查玩家是否已经获胜
        if self._player_score(PlayerColor.RED) == BOARD_N - 2 or \
           self._player_score(PlayerColor.BLUE) == BOARD_N - 2:
            return True
            
        return False
    
    @property
    def turn_limit_reached(self):
        """是否达到最大回合数"""
        return self.turn_count >= MAX_TURNS
    
    def _player_score(self, color):
        """计算指定玩家的得分"""
        # 这个方法需要根据底层 Board._player_score 的逻辑实现
        # 简化版：红色玩家需要到达底部，蓝色玩家需要到达顶部
        if color == PlayerColor.RED:
            return self._row_count(color, BOARD_N - 1)
        else:  # BLUE
            return self._row_count(color, 0)
    
    def _row_count(self, color, row):
        """计算指定行上指定颜色棋子的数量"""
        count = 0
        for c in range(BOARD_N):
            coord = Coord(row, c)
            if self[coord].state == color:
                count += 1
        return count
    
    def _get_all_mutations(self):
        """收集当前实例和所有父实例的修改"""
        mutations = dict(self._modified_cells)
        
        current = self._parent
        while current:
            for coord, state in current._modified_cells.items():
                if coord not in mutations:  # 只保留最早的修改
                    mutations[coord] = state
            current = current._parent
            
        return mutations
    
    def materialize(self):
        """将当前状态转换为实际的 Board 对象"""
        # 创建一个新的棋盘
        materialized = self._board.clone()
        
        # 应用所有修改
        mutations = self._get_all_mutations()
        for coord, state in mutations.items():
            materialized.set_cell_state(coord, state)
            
        # 确保回合颜色是正确的
        materialized.set_turn_color(self.turn_color)
        
        # 添加固定开局计数
        materialized._red_fixed_moves = self._red_fixed_moves
        materialized._blue_fixed_moves = self._blue_fixed_moves
            
        return materialized
        
    def iterate_cells(self):
        """
        迭代棋盘上的所有格子及其状态。
        模拟 dict.items() 的行为，返回 (Coord, CellState) 对。
        """
        for r in range(BOARD_N):
            for c in range(BOARD_N):
                coord = Coord(r, c)
                yield coord, self[coord]
                
    def get_cells_by_state(self, state_value):
        """
        获取特定状态的所有格子坐标。
        
        Args:
            state_value: 要查找的状态值，例如 PlayerColor.RED, PlayerColor.BLUE, "LilyPad", None
            
        Returns:
            一个包含满足条件的格子坐标的列表
        """
        result = []
        for coord, cell in self.iterate_cells():
            if cell.state == state_value:
                result.append(coord)
        return result 