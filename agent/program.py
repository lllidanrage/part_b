# COMP30024 Artificial Intelligence, Semester 1 2025
# Project Part B: Game Playing Agent

from referee.game import PlayerColor, Coord, Direction, \
    Action, MoveAction, GrowAction, Board

from .MCTS import MCTS, GameState

class Agent:
    """
    This class is the "entry point" for your agent, providing an interface to
    respond to various Freckers game events.
    """

    def __init__(self, color: PlayerColor, **referee: dict):
        """
        This constructor method runs when the referee instantiates the agent.
        Any setup and/or precomputation should be done here.
        """
        self._color = color
        self._board = Board() 
        
        match color:
            case PlayerColor.RED:
                print("Testing: I am playing as RED")
            case PlayerColor.BLUE:
                print("Testing: I am playing as BLUE")

    def action(self, **referee: dict) -> Action:
        """
        This method is called by the referee each time it is the agent's turn
        to take an action. It must always return an action object. 
        """
        # 创建当前游戏状态
        current_state = GameState(None, self._board)
        
        # 使用MCTS算法选择最佳动作
        mcts = MCTS(current_state)
        best_action = mcts.search(iterations=1000)
        
        # 如果找不到合法动作，则执行默认动作
        if best_action is None:
            match self._color:
                case PlayerColor.RED:
                    print("Testing: RED is playing a default GROW action")
                    return GrowAction()
                case PlayerColor.BLUE:
                    print("Testing: BLUE is playing a default GROW action")
                    return GrowAction()
        
        # 打印选择的动作
        match self._color:
            case PlayerColor.RED:
                print("Testing: RED is playing a MOVE action")
            case PlayerColor.BLUE:
                print("Testing: BLUE is playing a MOVE action")
        
        return best_action

    def update(self, color: PlayerColor, action: Action, **referee: dict):
        """
        This method is called by the referee after a player has taken their
        turn. You should use it to update the agent's internal game state. 
        """
        # 更新内部游戏状态
        self._board.apply_action(action)

        # 打印动作信息（仅用于调试）
        match action:
            case MoveAction(coord, dirs):
                dirs_text = ", ".join([str(dir) for dir in dirs])
                print(f"Testing: {color} played MOVE action:")
                print(f"  Coord: {coord}")
                print(f"  Directions: {dirs_text}")
            case GrowAction():
                print(f"Testing: {color} played GROW action")
            case _:
                raise ValueError(f"Unknown action type: {action}")
