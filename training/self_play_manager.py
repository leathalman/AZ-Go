import random

import numpy as np

from definitions import CONFIG_PATH
from go.go_game import GoGame
from utils.config_handler import ConfigHandler
from utils.print_debug import print_debug
from go.go_game import display


class SelfPlayManager:

    def __init__(self, neural_net, mcts):
        self.config = ConfigHandler(CONFIG_PATH)
        self.go_game = GoGame(self.config['board_size'])
        self.neural_net = neural_net
        self.mcts = mcts

    def execute_game(self):
        game_train_examples = []
        board = self.go_game.getInitBoard()
        current_player = 1
        turn_count = 0

        # TODO: Static method only supporting 7x7 board
        c_boards = [np.ones((7, 7)), np.zeros((7, 7))]
        x_boards, y_boards = self.go_game.init_x_y_boards()
        r = 0

        while r == 0:
            x_boards, y_boards = y_boards, x_boards
            turn_count += 1

            # Get the current board, current player's board, and game history at current state
            #canonical_board = self.go_game.getCanonicalForm(board, current_player)

            #player_board = (c_boards[0], c_boards[1]) if current_player == 1 else (c_boards[1], c_boards[0])
            #canonicalHistory, x_boards, y_boards = self.go_game.getCanonicalHistory(x_boards, y_boards,
            #                                                                        canonical_board, player_board)
            # set temperature variable and get move probabilities
            temp = int(turn_count < self.config["temperature_threshold"])

            # TODO: Is heuristic for full search sims vs fast sims acceptable?
            if random.random() <= 0.25:
                """num_sims = self.config["num_full_search_sims"]
                use_noise = True"""
                is_full_search = True
            else:
                """num_sims = self.config["num_fast_search_sims"]
                use_noise = False"""
                is_full_search = False

            """pi = self.mcts.getActionProb(canonical_board, canonicalHistory, x_boards, y_boards, player_board, use_noise,
                                         num_sims, temp=temp)"""
        
            pi = self.mcts.getActionProb(board, temp=temp, is_full_search=is_full_search)

            # TODO: Update temp to resemble the paper's implementation
            # choose a move
            if temp == 1:
                action = np.random.choice(len(pi), p=pi)
            else:
                action = np.argmax(pi)
            masked_pi = [0 for _ in range(self.go_game.getActionSize())]
            masked_pi[action] = 1
            # get different symmetries/rotations of the board if full search was done
            if is_full_search:
                canonicalHistory = board.get_canonical_history()
                sym = self.go_game.getSymmetries(canonicalHistory, masked_pi)
                for b, p in sym:
                    game_train_examples.append([b, board.current_player, p, None])

            # play the chosen move
            board = self.go_game.getNextState(board, action)

            r, score = self.go_game.getGameEndedSelfPlay(board.copy(), return_score=True,
                                                         enable_resignation_threshold=True)

            print_debug(f"Score: {score}, R: {r}")
            #print(f"Given pi = {pi}\nChose action = {action}")
            # print(display(board))
            bscore, wscore = self.go_game.getScore(board)
            # print(f"Score -- B: {bscore}   W: {wscore}")
            # print("\n")

        # return game result
        return [(x[0], x[2], r * ((-1) ** (x[1] != board.current_player))) for x in game_train_examples]
