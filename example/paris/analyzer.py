import pandas as pd
import numpy as np

class ParisAnalyzer:
    def __init__(self, threshold, number_of_bounds, cutoff_distance, reference_path, modes = ["car", "pt", "bike", "walk"]):
        self.threshold = threshold
        self.number_of_bounds = number_of_bounds
        self.cutoff_distance = cutoff_distance
        self.reference_path = reference_path
        self.modes = modes

    def prepare_reference(self, reference_path):
        df = pd.read_csv(reference_path, sep = ";")
        df["is_urban"] = (df["origin_departement_id"] == 75) & (df["destination_departement_id"] == 75)
        df["weight"] = df["trip_weight"]

        df = df[df["euclidean_distance"] > 0.0]
        return df

    def prepare_simulation(self, output_path):
        df = pd.read_csv("%s/trips.csv" % output_path, sep = ";")
        df["weight"] = 1.0

        df_urban = pd.read_csv("%s/urban.csv" % output_path, sep = ";")
        df = pd.merge(df, df_urban, on = ["person_id", "person_trip_id"])
        df["is_urban"] = df["urban_origin"] & df["urban_destination"]

        df = df[df["euclidean_distance"] > 0.0]
        return df

    def calculate_bounds(self, df):
        df = df[
            df["mode"].isin(self.modes) & (df["euclidean_distance"] <= self.cutoff_distance)
        ]

        distances = df["euclidean_distance"].values
        weights = df["weight"].values

        sorter = np.argsort(distances)
        distances = distances[sorter]
        weights = weights[sorter]

        cdf = np.cumsum(weights)
        cdf = cdf / np.sum(weights)

        return np.unique([0] + [
            np.max(distances[cdf <= p])
            for p in np.linspace(0.0, 1.0, self.number_of_bounds)[1:]
        ])

    def calculate_shares(self, df, bounds):
        totals = [
            df[
                (df["euclidean_distance"] >= q1) & (df["euclidean_distance"] < q2) &
                df["mode"].isin(self.modes)]["weight"].sum()
            for q1, q2 in zip(bounds, bounds[1:])
        ]

        counts = {
            mode : [df[
                (df["euclidean_distance"] >= q1) & (df["euclidean_distance"] < q2) &
                (df["mode"] == mode)]["weight"].sum()
            for q1, q2 in zip(bounds, bounds[1:]) ]
            for mode in self.modes
        }

        shares = {
            mode : np.nan_to_num(np.array(counts[mode]) / np.array(totals))
            for mode in self.modes
        }

        return shares

    def calculate_objective(self, reference_shares, simulation_shares):
        objective = 0.0

        for mode in self.modes:
            objective += np.sum(np.maximum(self.threshold,
                reference_shares[mode] - simulation_shares[mode]
            ))

        return objective

    def execute(self, output_path):
        df_reference = self.prepare_reference(self.reference_path)
        df_simulation = self.prepare_simulation(output_path)

        bounds = self.calculate_bounds(df_reference)

        # Regional shares
        region_reference_shares = self.calculate_shares(df_reference, bounds)
        region_simulation_shares = self.calculate_shares(df_simulation, bounds)
        region_objective = self.calculate_objective(region_reference_shares, region_simulation_shares)

        # Paris shares
        df_reference = df_reference[df_reference["is_urban"]]
        df_simulation = df_simulation[df_simulation["is_urban"]]

        paris_reference_shares = self.calculate_shares(df_reference, bounds)
        paris_simulation_shares = self.calculate_shares(df_simulation, bounds)
        paris_objective = self.calculate_objective(paris_reference_shares, paris_simulation_shares)

        # Total objective
        objective = 0.5 * (paris_objective + region_objective)

        return {
            "bounds": bounds,

            "region_reference_shares": region_reference_shares,
            "region_simulation_shares": region_simulation_shares,
            "region_objective": region_objective,

            "paris_reference_shares": paris_reference_shares,
            "paris_simulation_shares": paris_simulation_shares,
            "paris_objective": paris_objective,

            "objective": objective
        }

if __name__ == "__main__":
    analyzer = ParisAnalyzer(
        threshold = 0.05,
        number_of_bounds = 40,
        cutoff_distance = 40 * 1e3,
        reference_path = "/home/shoerl/gpe/data/pipeline_hts/hts_trips.csv")

    result = analyzer.execute("/home/shoerl/gpe/output_1pm/simulation_output")
    print(result)