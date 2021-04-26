from octras import Problem

import pandas as pd
import numpy as np

NAMES = [
    "betaCost_u_MU",
    "lambdaCostEuclideanDistance",

    "car.alpha_u",
    "car.betaTravelTime_u_min",
    "idfCar.betaInsideUrbanArea",
    "idfCar.betaCrossingUrbanArea",

    "pt.betaLineSwitch_u",
    "pt.betaInVehicleTime_u_min",
    "pt.betaWaitingTime_u_min",
    "pt.betaAccessEgressTime_u_min",

    "bike.alpha_u",
    "bike.betaTravelTime_u_min",
    "bike.betaAgeOver18_u_a",
    "idfBike.betaInsideUrbanArea",

    "walk.alpha_u",
    "walk.betaTravelTime_u_min",
]

BOUNDS = [
    (-5.0, 0.0),
    (-0.5, 0.0),

    (-2.0, 2.0),
    (-1.0, 0.0),
    (-1.0, 0.0),
    (-1.0, 0.0),

    (-1.0, 0.0),
    (-1.0, 0.0),
    (-1.0, 0.0),
    (-1.0, 0.0),

    (-2.0, 2.0),
    (-1.0, 0.0),
    (-1.0, 0.0),
    (-1.0, 0.0),

    (-2.0, 2.0),
    (-1.0, 0.0)
]

INITIALS = [
    -0.206,
    -0.4,

    1.35,
    -0.06,
    -0.5,
    -1.0,

    -0.17,
    -0.017,
    -0.0484,
    -0.0804,

    -2.0,
    -0.05,
    -0.0496,
    1.5,

    1.43,
    -0.15
]

class ParisProblem(Problem):
    """
        Here we define an optimization problem for MATSim. Namely, we want to
        push the mode shares of car and public transport to each 30% by playing
        around with the mode constants.
    """

    def __init__(self, analyzer, threads, iterations, config_path):
        """
            We pass some desired reference values and save them.
        """

        # We need to provide some mandatory information
        self.number_of_parameters = 16
        self.number_of_states = 1

        # We can provide some information that is passed to the output
        self.information = dict(problem = "ParisProblem")

        # We can provide the reference state. Currently, it is not used in any
        # optimizer, but it is helpful for plotting optimization results as
        # the existing plotting scripts will know how to use this information.
        self.reference_state = 0

        self.initial = INITIALS
        self.bounds = BOUNDS

        self.analyzer = analyzer
        self.threads = threads
        self.iterations = iterations
        self.config_path = config_path

    def prepare(self, x):
        """
            This function gets a vector of numeric parameters. Our task is to
            translate those numbers into actual config instructions for
            MATSim.
        """

        # First we need to pass some parameters to the simulator
        parameters = dict(config = { # We provide --config: parameters to the simulation
            "qsim.numberOfThreads": self.threads,
            "global.numberOfThreads": self.threads,
            "eqasim.tripAnalysisInterval": self.iterations,
            "controler.writeTripsInterval": 0,
            "linkStats.writeLinkStatsInterval": 0,
            "counts.writeCountsInterval": 0
        }, iterations = self.iterations)

        arguments = []

        for value, name in zip(x, NAMES):
            arguments.append("--mode-choice-parameter:%s" % name)
            arguments.append(str(value))

        arguments += [
            "--mode-choice-parameter:car.constantAccessEgressWalkTime_min", "4.0",
            "--mode-choice-parameter:car.constantParkingSearchPenalty_min", "4.0",
        ]

        arguments += [
            "--config-path", self.config_path,
            #"--use-epsilon",
            #"--convergence-threshold", "0.05"    ONLY WORKS IN DEVELOPMENT VERSION
        ]

        parameters["arguments"] = arguments

        return parameters

    def evaluate(self, x, path):
        """
            This is the objective function. It receives the numeric parameters
            as the first argument and the output of the simulator as the
            second argument. In this case, we rely on the fact that the
            standard MATSim simulator just returns the path of the output
            directory of the simulation.
        """

        result = self.analyzer.execute(path)
        return result["objective"], None, result
