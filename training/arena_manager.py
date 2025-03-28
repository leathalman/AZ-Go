from definitions import CONFIG_PATH
from go.go_game import GoGame, display
from logger.gtp_logger import GTPLogger, GameType, PlayerType
from utils.config_handler import ConfigHandler
import numpy as np

class ArenaManager:

    def __init__(self, player1, player2, mcts1, mcts2):
        self.config = ConfigHandler(CONFIG_PATH)
        self.player1 = player1  # prev_mcts player
        self.player2 = player2  # curr_mcts player
        self.mcts1 = mcts1
        self.mcts2 = mcts2
        self.game = GoGame(self.config["board_size"], is_arena_game=True)
        self.gtp_logger = GTPLogger()

    def play_games(self, num_games):
        threshold = num_games * (self.config['acceptance_threshold'])
        self.gtp_logger.set_players(PlayerType.PREVIOUS, PlayerType.CURRENT)

        one_wins, two_wins, draws = 0, 0, 0

        for i in range(num_games):
            game_result = self.play_game()

            if (i % 2) == 0:
                if game_result == 1:
                    one_wins += 1
                elif game_result == -1:
                    two_wins += 1
                else:
                    draws += 1
            else:
                if game_result == -1:
                    one_wins += 1
                elif game_result == 1:
                    two_wins += 1
                else:
                    draws += 1

            # If one of the models meets the threshold for games won AND there is more than 1 game left to play,
            # return from arena play
            if one_wins >= threshold or two_wins >= threshold:
                return one_wins, two_wins, draws

            # switch black and white players
            self.player1, self.player2 = self.player2, self.player1

            # how does this handle jumping between generations? works fine for one iteration...
            if self.gtp_logger.player_black == PlayerType.PREVIOUS:
                self.gtp_logger.player_black = PlayerType.CURRENT
                self.gtp_logger.player_white = PlayerType.PREVIOUS
            else:
                self.gtp_logger.player_black = PlayerType.PREVIOUS
                self.gtp_logger.player_white = PlayerType.CURRENT

        return one_wins, two_wins, draws

    def play_game(self):
        print("Arena Game Started")
        self.game = GoGame(self.config["board_size"], is_arena_game=True)
        board = self.game.getInitBoard()
        c_boards = [np.ones((7, 7)), np.zeros((7, 7))]
        x_boards, y_boards = self.game.init_x_y_boards()
        players = [self.player2, None, self.player1]

        self.clear_mcts()

        while self.game.getGameEndedArena(board, False, self.mcts1, self.mcts2) == 0:
            # Code for old MCTS
            x_boards, y_boards = y_boards, x_boards
            canonicalBoard = self.game.getCanonicalForm(board, board.current_player)
            player_board = (c_boards[0], c_boards[1]) if board.current_player == 1 else (c_boards[1], c_boards[0])
            canonicalHistory, x_boards, y_boards = self.game.getCanonicalHistory(x_boards, y_boards,
                                                                                 canonicalBoard, player_board)
            # print("History used to make move: ", canonicalHistory)

            # action = players[board.current_player + 1](board)
            #Code for old MCTS
            action = players[board.current_player + 1](board, canonicalBoard, canonicalHistory, x_boards, y_boards, player_board, self.config["num_full_search_sims"])
            self.gtp_logger.add_action(action, board)
            board = self.game.getNextState(board, action)
        #     print(f"Player: {board.current_player}, Move: {action}")
        #     print(display(board))
        #     print("\n\n")
        # print("\n\n")

        self.gtp_logger.save_sgf(GameType.ARENA)

        result, score = self.game.getGameEndedArena(board, True, self.mcts1, self.mcts2)
        old_score_system = self.game.getScore_old_system(board.copy())

        # print(f"Old scoring :: Black Score: {old_score_system[0]}, White Score: {old_score_system[1]}")
        # print(f"Tromp Taylor :: Black Score: {score[0]}, White Score: {score[1]}")
        return result

    def clear_mcts(self):
        if self.mcts1:
            self.mcts1.clear()
        if self.mcts2:
            self.mcts2.clear()
