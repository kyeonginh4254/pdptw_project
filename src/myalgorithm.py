import time
import json
import copy
import numpy as np
import gurobipy as gp
from gurobipy import GRB
from util import *
from lib.bundle_generator_2 import get_all_bundles

def algorithm(K, all_orders, all_riders, dist_mat, timelimit=60):

    start_time = time.time()

    # Update rider's service time based on distance and speed
    for r in all_riders:
        r.T = np.round(dist_mat / r.speed + r.service_time)

    # Generate all feasible bundles using the reference code's get_all_bundles function

    all_bundles = []
    for i, rider in enumerate(all_riders):
        print(f">>> Generating {rider.type} bundles ... ({time.time() - start_time:.4f}s)")
        all_bundles.extend(get_all_bundles(K, all_orders, rider, dist_mat))
        

    print(f">>> Total bundles generated: {len(all_bundles)} bundles ({time.time() - start_time:.4f}s)")

    # Formulate Set Partitioning Problem using Gurobi
    print(f">>> Formulating the Set Partitioning Problem ... ({time.time() - start_time:.4f}s)")

    model = gp.Model("SetPartitioning")
    model.setParam('OutputFlag', 0)

    # Create a list of all orders' IDs for constraint definitions
    order_ids = set(order.id for order in all_orders)

    # Create variables: one binary variable per bundle
    bundle_vars = {}
    for idx, bundle in enumerate(all_bundles):
        var = model.addVar(vtype=GRB.BINARY, name=f"Bundle_{idx}")
        bundle_vars[idx] = var

    model.update()

    # Add constraints: Each order must be covered exactly once
    print(f">>> Adding constraints to ensure each order is covered exactly once ... ({time.time() - start_time:.4f}s)")
    for order_id in order_ids:
        # Find all bundles that include this order
        covering_bundles = [idx for idx, bundle in enumerate(all_bundles) if order_id in bundle.shop_seq]
        if not covering_bundles:
            raise ValueError(f"No bundle covers order {order_id}.")
        model.addConstr(
            gp.quicksum(bundle_vars[idx] for idx in covering_bundles) == 1,
            name=f"Order_{order_id}_coverage"
        )

    # **Add Rider Limit Constraints**
    print(f">>> Adding rider limit constraints ... ({time.time() - start_time:.4f}s)")

    # Step 1: Aggregate available riders by type
    rider_available = {}
    for rider in all_riders:
        if rider.type not in rider_available:
            rider_available[rider.type] = rider.available_number
        else:
            rider_available[rider.type] += rider.available_number

    # Step 2: Map rider types to their corresponding bundle indices
    type_to_bundles = {}
    for idx, bundle in enumerate(all_bundles):
        rider_type = bundle.rider.type
        if rider_type not in type_to_bundles:
            type_to_bundles[rider_type] = []
        type_to_bundles[rider_type].append(idx)

    # Step 3: Add constraints to ensure rider limits are not exceeded
    for rider_type, available in rider_available.items():
        if rider_type in type_to_bundles:
            model.addConstr(
                gp.quicksum(bundle_vars[idx] for idx in type_to_bundles[rider_type]) <= available,
                name=f"RiderLimit_{rider_type}"
            )
        else:
            # No bundles for this rider type, no action needed
            pass

    # Define the objective: Minimize total cost
    print(f">>> Defining the objective function ... ({time.time() - start_time:.4f}s)")
    model.setObjective(
        gp.quicksum(bundle.cost * bundle_vars[idx] for idx, bundle in enumerate(all_bundles)),
        GRB.MINIMIZE
    )

    # Set time limit
    model.setParam('TimeLimit', timelimit)

    # Optimize the model
    print(f">>> Starting optimization with Gurobi ... ({time.time() - start_time:.4f}s)")
    model.optimize()

    if model.status != GRB.OPTIMAL and model.status != GRB.TIME_LIMIT:
        print("No optimal solution found.")
        return []

    # Extract the solution
    print(f">>> Extracting the solution ... ({time.time() - start_time:.4f}s)")
    solution_bundles = []
    for idx, var in bundle_vars.items():
        if var.X > 0.5:  # If the bundle is selected
            bundle = all_bundles[idx]
            solution_bundles.append(bundle)

    best_obj = sum(bundle.cost for bundle in solution_bundles)

    # Format the solution as required
    solution = [
        [bundle.rider.type, bundle.shop_seq, bundle.dlv_seq]
        for bundle in solution_bundles
    ]

    return solution
