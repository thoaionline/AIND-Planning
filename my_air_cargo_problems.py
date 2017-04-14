from aimacode.logic import PropKB
from aimacode.planning import Action
from aimacode.search import (
    Node, Problem,
)
from aimacode.utils import expr
from lp_utils import (
    FluentState, encode_state, decode_state,
)
from my_planning_graph import PlanningGraph


class AirCargoProblem(Problem):
    def __init__(self, cargos, planes, airports, initial: FluentState, goal: list):
        """

        :param cargos: list of str
            cargos in the problem
        :param planes: list of str
            planes in the problem
        :param airports: list of str
            airports in the problem
        :param initial: FluentState object
            positive and negative literal fluents (as expr) describing initial state
        :param goal: list of expr
            literal fluents required for goal test
        """
        self.state_map = initial.pos + initial.neg
        self.initial_state_TF = encode_state(initial, self.state_map)
        Problem.__init__(self, self.initial_state_TF, goal=goal)
        self.cargos = cargos
        self.planes = planes
        self.airports = airports
        self.actions_list = self.get_actions()

    def get_actions(self):
        '''
        This method creates concrete actions (no variables) for all actions in the problem
        domain action schema and turns them into complete Action objects as defined in the
        aimacode.planning module. It is computationally expensive to call this method directly;
        however, it is called in the constructor and the results cached in the `actions_list` property.

        Returns:
        ----------
        list<Action>
            list of Action objects
        '''

        # concrete actions definition: specific literal action that does not include variables as with the schema
        # for example, the action schema 'Load(c, p, a)' can represent the concrete actions 'Load(C1, P1, SFO)'
        # or 'Load(C2, P2, JFK)'.  The actions for the planning problem must be concrete because the problems in
        # forward search and Planning Graphs must use Propositional Logic

        def load_actions():
            '''Create all concrete Load actions and return a list

            :return: list of Action objects
            '''
            loads = []
            for cargo in self.cargos:
                for plane in self.planes:
                    for airport in self.airports:
                        precond_pos = [
                            expr("At({}, {})".format(cargo, airport)),
                            expr("At({}, {})".format(plane, airport)),
                        ]
                        precond_neg = []
                        effect_add = [
                            expr("In({}, {})".format(cargo, plane))
                        ]
                        effect_rem = [
                            expr("At({}, {})".format(cargo, plane))
                        ]

                        load = Action(
                            expr("Load({}, {}, {})".format(cargo, plane, airport)),
                            [precond_pos, precond_neg],
                            [effect_add, effect_rem]
                        )

                        loads.append(load)

            return loads

        def unload_actions():
            '''Create all concrete Unload actions and return a list

            :return: list of Action objects
            '''
            unloads = []
            for cargo in self.cargos:
                for plane in self.planes:
                    for airport in self.airports:
                        precond_pos = [
                            expr("In({}, {})".format(cargo, plane)),
                            expr("At({}, {})".format(plane, airport)),
                        ]
                        precond_neg = []
                        effect_add = [
                            expr("At({}, {})".format(cargo, airport))
                        ]
                        effect_rem = [
                            expr("In({}, {})".format(cargo, airport))
                        ]

                        unload = Action(
                            expr("Unload({}, {}, {})".format(cargo, plane, airport)),
                            [precond_pos, precond_neg],
                            [effect_add, effect_rem]
                        )

                        unloads.append(unload)

            return unloads

        def fly_actions():
            '''Create all concrete Fly actions and return a list

            :return: list of Action objects
            '''
            flys = []
            for fr in self.airports:
                for to in self.airports:
                    if fr != to:
                        for p in self.planes:
                            precond_pos = [expr("At({}, {})".format(p, fr)),
                                           ]
                            precond_neg = []
                            effect_add = [expr("At({}, {})".format(p, to))]
                            effect_rem = [expr("At({}, {})".format(p, fr))]
                            fly = Action(expr("Fly({}, {}, {})".format(p, fr, to)),
                                         [precond_pos, precond_neg],
                                         [effect_add, effect_rem])
                            flys.append(fly)
            return flys

        return load_actions() + unload_actions() + fly_actions()

    def actions(self, state: str) -> list:
        """ Return the actions that can be executed in the given state.

        :param state: str
            state represented as T/F string of mapped fluents (state variables)
            e.g. 'FTTTFF'
        :return: list of Action objects
        """
        possible_actions = []

        state = decode_state(state,self.state_map)

        for action in self.actions_list:
            ok = True
            for precond_pos in action.precond_pos:
                if not (precond_pos in state.pos):
                    ok = False
                    break
            for precond_nev in action.precond_neg:
                if not (precond_nev in state.neg):
                    ok = False
                    break
            if ok:
                possible_actions.append(action)

        return possible_actions

    def result(self, state: str, action: Action):
        """ Return the state that results from executing the given
        action in the given state. The action must be one of
        self.actions(state).

        :param state: state entering node
        :param action: Action applied
        :return: resulting state after action
        """

        state = decode_state(state, self.state_map)

        for effect_rem in action.effect_rem:
            state.pos.remove(effect_rem)
            state.neg.append(effect_rem)
        for effect_add in action.effect_add:
            state.pos.append(effect_add)
            state.neg.remove(effect_add)

        return encode_state(state, self.state_map)

    def goal_test(self, state: str) -> bool:
        """ Test the state to see if goal is reached

        :param state: str representing state
        :return: bool
        """
        kb = PropKB()
        kb.tell(decode_state(state, self.state_map).pos_sentence())
        for clause in self.goal:
            if clause not in kb.clauses:
                return False
        return True

    def h_1(self, node: Node):
        # note that this is not a true heuristic
        h_const = 1
        return h_const

    def h_pg_levelsum(self, node: Node):
        '''
        This heuristic uses a planning graph representation of the problem
        state space to estimate the sum of all actions that must be carried
        out from the current state in order to satisfy each individual goal
        condition.
        '''
        # requires implemented PlanningGraph class
        pg = PlanningGraph(self, node.state)
        pg_levelsum = pg.h_levelsum()
        return pg_levelsum

    def h_ignore_preconditions(self, node: Node):
        '''
        This heuristic estimates the minimum number of actions that must be
        carried out from the current state in order to satisfy all of the goal
        conditions by ignoring the preconditions required for an action to be
        executed.
        '''

        count = 0

        node_state = decode_state(node.state, self.state_map).pos

        for goal_expresion in self.goal:
            if not (goal_expresion in node_state):
                count += 1

        return count


def air_cargo_p1() -> AirCargoProblem:
    cargos = ['C1', 'C2']
    planes = ['P1', 'P2']
    airports = ['JFK', 'SFO']
    pos = [expr('At(C1, SFO)'),
           expr('At(C2, JFK)'),
           expr('At(P1, SFO)'),
           expr('At(P2, JFK)'),
           ]
    neg = [expr('At(C2, SFO)'),
           expr('In(C2, P1)'),
           expr('In(C2, P2)'),
           expr('At(C1, JFK)'),
           expr('In(C1, P1)'),
           expr('In(C1, P2)'),
           expr('At(P1, JFK)'),
           expr('At(P2, SFO)'),
           ]
    init = FluentState(pos, neg)
    goal = [expr('At(C1, JFK)'),
            expr('At(C2, SFO)'),
            ]
    return AirCargoProblem(cargos, planes, airports, init, goal)


def air_cargo_p2() -> AirCargoProblem:
    cargos = ['C1','C2','C3']
    planes = ['P1','P2','P3']
    airports = ['JFK', 'SFO', 'ATL']
    plane_to_airport = {
        'P1': 'SFO',
        'P2': 'JFK',
        'P3': 'ATL'
    }
    cargo_to_airport = {
        'C1': 'SFO',
        'C2': 'JFK',
        'C3': 'ATL',
    }
    pos = []
    neg = []
    for plane, this_airport in plane_to_airport:
        for other_airport in airports:
            if other_airport == this_airport:
                pos.append(expr('At({}, {})'.format(plane, this_airport)))
            else:
                neg.append(expr('At({}, {})'.format(plane, other_airport)))

    for cargo, this_airport in cargo_to_airport:
        for other_airport in airports:
            if this_airport == other_airport:
                pos.append(expr('At({}, {})'.format(cargo, this_airport)))
            else:
                neg.append(expr('At({}, {})'.format(cargo, other_airport)))

        for plane in planes:
            neg.append(expr('In({}, {})'.format(cargo, plane)))

    init = FluentState(pos,neg)

    goal = [
        expr('At(C1, JFK)'),
        expr('At(C2, SFO)'),
        expr('At(C3, SFO)'),
    ]
    return AirCargoProblem(cargos, planes, airports, init, goal)


def air_cargo_p3() -> AirCargoProblem:
    # TODO implement Problem 3 definition
    pass
