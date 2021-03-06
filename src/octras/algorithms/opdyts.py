import numpy as np
import scipy.optimize as opt

import copy

import logging
logger = logging.getLogger(__name__)

class ApproximateSelectionProblem:
    def __init__(self, v, w, deltas, objectives):
        self.deltas = deltas
        self.objectives = objectives
        self.w = w
        self.v = v

    def get_uniformity_gap(self, alpha):
        return np.sum(alpha**2)

    def get_equilibrium_gap(self, alpha):
        return np.sqrt(np.sum((alpha[:, np.newaxis] * self.deltas)**2))

    def get_transient_performance(self, alpha):
        return np.sum(alpha * self.objectives)

    def get_objective(self, alpha):
        objective = self.get_transient_performance(alpha)
        objective += self.v * self.get_equilibrium_gap(alpha)
        objective += self.w * self.get_uniformity_gap(alpha)
        return objective

    def solve(self):
        alpha = np.ones((len(self.objectives),)) / len(self.objectives)
        result = opt.minimize(self.get_objective, alpha, constraints = [
            { "type": "eq", "fun": lambda alpha: np.sum(alpha) - 1.0 },
        ], bounds = [(0.0, 1.0)] * len(self.objectives), options = { "disp": False })

        if not result.success:
            print("Deltas:", self.deltas)
            print("Objectives:", self.objectives)
            print("v, w:", self.v, self.w)
            raise RuntimeError("Could not solve Approximate Selection Problem")

        return result.x

class AdaptationProblem:
    def __init__(self, weight, selection_performance, transient_performance, equilibrium_gap, uniformity_gap):
        self.weight = weight
        self.selection_performance = selection_performance
        self.transient_performance = transient_performance
        self.uniformity_gap = uniformity_gap
        self.equilibrium_gap = equilibrium_gap

    def get_objective(self, vw):
        R = len(self.selection_performance)
        v, w = vw

        objective = 0.0

        for r in range(R):
            local_objective = np.abs(self.transient_performance[r] - self.selection_performance[r])
            local_objective -= (v * self.equilibrium_gap[r] + w * self.uniformity_gap[r])
            local_objective = np.sum(local_objective**2)
            objective += self.weight**(R - r) * local_objective

        return objective

    def solve(self):
        vw = np.array([0.0, 0.0])

        result = opt.minimize(self.get_objective, vw, bounds = [
            (0.0, 1.0), (0.0, 1.0)
        ], options = { "disp": False })

        if not result.success:
            raise RuntimeError("Could not solve Adaptation Problem")

        return result.x

class Opdyts:
    def __init__(self, evaluator, candidate_set_size, number_of_transitions, perturbation_length = 1.0, adaptation_weight = 0.3, seed = None):
        self.evaluator = evaluator
        self.problem = self.evaluator.problem

        self.iteration = 0
        self.v, self.w = 0.0, 0.0

        self.adaptation_weight = adaptation_weight
        self.adaptation_transient_performance = []
        self.adaptation_equilibrium_gap = []
        self.adaptation_uniformity_gap = []
        self.adaptation_selection_performance = []

        self.candidate_set_size = candidate_set_size
        self.perturbation_length = perturbation_length
        self.number_of_transitions = number_of_transitions

        self.information = { "algorithm": "Opdyts" }

        if self.candidate_set_size % 2 != 0:
            raise RuntimeError("This Opdyts implementation expects candiate set size as a multiple of 2.")

        if not hasattr(self.problem, "initial"):
            raise RuntimeError("Opdyts expects the problem to provide initial parameters.")

        if not hasattr(self.problem, "number_of_states"):
            raise RuntimeError("Opdyts expects the problem to provide number of states.")

        self.initial = self.problem.initial

        self.initial_identifier = None
        self.initial_objective = None
        self.initial_state = None
        self.initial_parameters = None

        self.random = np.random.RandomState(seed)

    def advance(self):
        if self.iteration == 0:
            logger.info("Initializing Opdyts")

            self.initial_parameters = self.problem.initial
            self.initial_identifier = self.evaluator.submit(self.initial_parameters,
                { "iterations": 1 }, { "type": "initial", "transient": True }
            )
            self.initial_objective, self.initial_state = self.evaluator.get(self.initial_identifier)

        self.iteration += 1
        logger.info("Starting Opdyts iteration %d" % self.iteration)

        # Create new set of candidate parameters
        candidate_parameters = np.zeros((self.candidate_set_size, self.problem.number_of_parameters))

        for c in range(0, self.candidate_set_size, 2):
            direction = self.random.random_sample(size = (self.problem.number_of_parameters,)) * 2.0 - 1.0
            candidate_parameters[c] = self.initial_parameters + direction * self.perturbation_length
            candidate_parameters[c + 1] = self.initial_parameters + direction * self.perturbation_length

        # Find initial candiate states
        candidate_identifiers = []
        candidate_states = np.zeros((self.candidate_set_size, self.problem.number_of_states))
        candidate_deltas = np.zeros((self.candidate_set_size, self.problem.number_of_states))
        candidate_objectives = np.zeros((self.candidate_set_size,))
        candidate_transitions = np.ones((self.candidate_set_size,))

        annotations = {
            "type": "candidate", "v": self.v, "w": self.w,
            "transient": True, "iteration": self.iteration
        }

        for c in range(self.candidate_set_size):
            candidate_annotations = copy.copy(annotations)
            candidate_annotations.update({ "candidate": c })

            candidate_identifiers.append(self.evaluator.submit(candidate_parameters[c], {
                #"iterations": transition_iterations,
                "restart": self.initial_identifier
            }, candidate_annotations))

        self.evaluator.wait()

        for c in range(self.candidate_set_size):
            candidate_objectives[c], candidate_states[c] = self.evaluator.get(candidate_identifiers[c])
            candidate_deltas[c] = candidate_states[c] - self.initial_state

        # Advance candidates
        local_adaptation_transient_performance = []
        local_adaptation_equilibrium_gap = []
        local_adaptation_uniformity_gap = []

        while np.max(candidate_transitions) < self.number_of_transitions:
            # Approximate selection problem
            selection_problem = ApproximateSelectionProblem(self.v, self.w, candidate_deltas, candidate_objectives)
            alpha = selection_problem.solve()

            transient_performance = selection_problem.get_transient_performance(alpha)
            equilibrium_gap = selection_problem.get_equilibrium_gap(alpha)
            uniformity_gap = selection_problem.get_uniformity_gap(alpha)

            local_adaptation_transient_performance.append(transient_performance)
            local_adaptation_equilibrium_gap.append(equilibrium_gap)
            local_adaptation_uniformity_gap.append(uniformity_gap)

            logger.info(
                "Transient performance: %f, Equilibirum gap: %f, Uniformity_gap: %f",
                transient_performance, equilibrium_gap, uniformity_gap)

            cumulative_alpha = np.cumsum(alpha)
            c = np.sum(self.random.random_sample() > cumulative_alpha) # TODO: Not deterministic!

            logger.info("Transitioning candidate %d", c)
            candidate_transitions[c] += 1
            transient = candidate_transitions[c] < self.number_of_transitions

            annotations.update({
                "type": "transition",
                "candidate": c, "transient_performance": transient_performance,
                "equilibrium_gap": equilibrium_gap, "uniformity_gap": uniformity_gap,
                "transient": transient
            })

            # Advance selected candidate
            identifier = self.evaluator.submit(candidate_parameters[c], {
                #"iterations": transition_iterations,
                "restart": candidate_identifiers[c]
            }, annotations)

            new_objective, new_state = self.evaluator.get(identifier)
            self.evaluator.clean(candidate_identifiers[c])

            candidate_deltas[c] = new_state - candidate_states[c]
            candidate_states[c], candidate_objectives[c] = new_state, new_objective
            candidate_identifiers[c] = identifier

        index = np.argmax(candidate_transitions)
        logger.info("Solved selection problem with candidate %d", index)

        for c in range(self.candidate_set_size):
            if c != index:
                self.evaluator.clean(candidate_identifiers[c])

        self.evaluator.clean(self.initial_identifier)
        self.initial_identifier = candidate_identifiers[index]
        self.initial_state = candidate_states[index]
        self.initial_parameters = candidate_parameters[index]

        self.adaptation_selection_performance.append(candidate_objectives[index])
        self.adaptation_transient_performance.append(np.array(local_adaptation_transient_performance))
        self.adaptation_equilibrium_gap.append(np.array(local_adaptation_equilibrium_gap))
        self.adaptation_uniformity_gap.append(np.array(local_adaptation_uniformity_gap))

        adaptation_problem = AdaptationProblem(self.adaptation_weight, self.adaptation_selection_performance, self.adaptation_transient_performance, self.adaptation_equilibrium_gap, self.adaptation_uniformity_gap)
        self.v, self.w = adaptation_problem.solve()

        logger.info("Solved Adaptation Problem. v = %f, w = %f", self.v, self.w)
