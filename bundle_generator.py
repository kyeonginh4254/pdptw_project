import time
import json
from util import *
import copy

def test_route_feasibility_custom(all_orders, rider, shop_seq, dlv_seq):
    total_vol = sum(all_orders[k].volume for k in shop_seq)
    if total_vol > rider.capa:
        # Capacity overflow!
        return -1 # Capacity infeasibility

    K = len(all_orders)

    pickup_times = {}

    k = shop_seq[0]
    t = all_orders[k].order_time + all_orders[k].cook_time # order time + order cook time
    pickup_times[k] = t
    for next_k in shop_seq[1:]:
        t = max(t + rider.T[k, next_k], all_orders[next_k].ready_time) # max{travel time + service time, ready time}
        pickup_times[next_k] = t
                
        k = next_k

    dlv_times = {}

    k = dlv_seq[0]
    t += rider.T[shop_seq[-1], k + K]

    dlv_times[k] = t
        
    for next_k in dlv_seq[1:]:
        t += rider.T[k + K, next_k + K]

        dlv_times[next_k] = t

        k = next_k

    for k, dlv_time in dlv_times.items():
        if dlv_time > all_orders[k].deadline:
            return -2 # Deadline infeasibility
    
    return 0

def get_total_distance(dist_mat, shop_seq, dlv_seq, K):
    return sum(dist_mat[i,j] for (i,j) in zip(shop_seq[:-1], shop_seq[1:])) + dist_mat[shop_seq[-1], dlv_seq[0]+K] + sum(dist_mat[i+K,j+K] for (i,j) in zip(dlv_seq[:-1], dlv_seq[1:]))

# (K, all_orders, car_rider, dist_mat)
def get_all_bundles(K, all_orders, rider, dist_mat):
    """
    최신화: 2024-07-18
    기능: 특정 rider 종류에 대해 가능한 모든 Bundle 조합을 depth별로 나누어 return
    input:
        all_orders(list) : Order 객체의 list인 ALL_ORDERS
        rider(Rider) : 구하고자 하는 Rider 객체
        save_file_name(str) : bundle들을 json파일로 저장하고자 할 때, .json 파일의 이름. 확장명(.json)없이 파일 이름만 전달
        save_path(str) : 저장 위치
    output:
        bundles(dict) : list of tuple이 하나의 Bundle로, 그 Bundle들이 다시 list로 묶여 depth 별로 정렬된 dictionary 객체
    """
    K = len(all_orders)

    nodes = set()
    bundles = {1:[]}

    checkpoint = time.time()

    print(f"Calculating {rider.type} bundles ...")

    cur_depth = 1
    for order in all_orders:
        if test_route_feasibility_custom(all_orders, rider, [order.id], [order.id]) == 0:
            nodes.add(order.id)
    for node in nodes:
        cand = nodes.copy()
        cand.discard(node)
        bundles[1].append(
            {
                "seq" : ([node], [node]),
                "candidate" : {
                    "ff" : cand,
                    "bf" : cand,
                    "fb" : cand,
                    "bb" : cand
                }
            }
        )
    
    while(len(bundles[cur_depth]) != 0):
        print(f"[{rider.type} {cur_depth}] {len(bundles[cur_depth])} bundles ({time.time()-checkpoint:.4f}s)")
        cur_depth += 1
        bundles[cur_depth] = []
        comparison_dict = {}
        cand = {}
        # bundle_history 제거

        for i in range(len(bundles[cur_depth-1])): # 여기서 bundle은, key 'seq'와 'candidate'로 이루어진 dictionary임
            bundle = bundles[cur_depth-1][i]
            seq_to_tuple = tuple([item for sublist in bundle["seq"] for item in sublist])
            cand[seq_to_tuple] = {
                "ff" : set(),
                "bf" : set(),
                "fb" : set(),
                "bb" : set()
            }
            shop, deli = bundle['seq']
            cur_usage = []

            # 4 cases candidate iteration
            for node in bundle['candidate']['ff']: # 여기서 node는, 이전 depth에서 앞, 앞에 붙을 수 있던 후보 node
                shop_seq = [node]+shop
                dlv_seq = [node]+deli

                # bundle_history 관련 코드 제거
                
                if test_route_feasibility_custom(all_orders, rider, shop_seq, dlv_seq) == 0:
                    sorted_shop_seq = tuple(sorted(shop_seq)) + (shop_seq[0], shop_seq[-1], dlv_seq[0], dlv_seq[-1])
                    # add to comparison_dict
                    total_dist = get_total_distance(dist_mat, shop_seq, dlv_seq, K)
                    comparison_dict[sorted_shop_seq] = {
                            "cost" : total_dist,
                            "seq" : (shop_seq, dlv_seq),
                            "used" : node,
                            "bundle_num" : i
                        }

                    cand[seq_to_tuple]["ff"].add(node)
                
                # else 조건 제거

            for node in bundle['candidate']['bf']:
                shop_seq = shop+[node]
                dlv_seq = [node]+deli

                # bundle_history 관련 코드 제거

                if test_route_feasibility_custom(all_orders, rider, shop + [node], [node] + deli) == 0:
                    sorted_shop_seq = tuple(sorted(shop_seq)) + (shop_seq[0], shop_seq[-1], dlv_seq[0], dlv_seq[-1])
                    # add to comparison_dict
                    total_dist = get_total_distance(dist_mat, shop_seq, dlv_seq, K)
                    comparison_dict[sorted_shop_seq] = {
                            "cost" : total_dist,
                            "seq" : (shop_seq, dlv_seq),
                            "used" : node,
                            "bundle_num" : i
                        }
                    cand[seq_to_tuple]["bf"].add(node)
                
                # else 조건 제거

            for node in bundle['candidate']['fb']:
                shop_seq = [node]+shop
                dlv_seq = deli+[node]

                # bundle_history 관련 코드 제거

                if test_route_feasibility_custom(all_orders, rider, [node] + shop, deli + [node]) == 0:
                    sorted_shop_seq = tuple(sorted(shop_seq)) + (shop_seq[0], shop_seq[-1], dlv_seq[0], dlv_seq[-1])
                    # add to comparison_dict
                    total_dist = get_total_distance(dist_mat, shop_seq, dlv_seq, K)
                    comparison_dict[sorted_shop_seq] = {
                            "cost" : total_dist,
                            "seq" : (shop_seq, dlv_seq),
                            "used" : node,
                            "bundle_num" : i
                        }
                    cand[seq_to_tuple]["fb"].add(node)
                
                # else 조건 제거

            for node in bundle['candidate']['bb']:
                shop_seq = shop + [node]
                dlv_seq = deli + [node]

                # bundle_history 관련 코드 제거

                if test_route_feasibility_custom(all_orders, rider, shop + [node], deli + [node]) == 0:
                    sorted_shop_seq = tuple(sorted(shop_seq)) + (shop_seq[0], shop_seq[-1], dlv_seq[0], dlv_seq[-1])
                    # add to comparison_dict
                    total_dist = get_total_distance(dist_mat, shop_seq, dlv_seq, K)
                    comparison_dict[sorted_shop_seq] = {
                            "cost" : total_dist,
                            "seq" : (shop_seq, dlv_seq),
                            "used" : node,
                            "bundle_num" : i
                        }
                    cand[seq_to_tuple]["bb"].add(node)
                
                # else 조건 제거

        # append to bundles, iterating cur_usage
        for sorted_shop_seq in comparison_dict.keys():
            new_cand = {}

            # find subset bundles of the bundle we're currently adding
            shop_seq = comparison_dict[sorted_shop_seq]["seq"][0]
            dlv_seq = comparison_dict[sorted_shop_seq]["seq"][1]
            subset_bundles = []

            for s in shop_seq:
                temp_shop = shop_seq.copy()
                temp_dlv = dlv_seq.copy()
                temp_shop.remove(s)
                temp_dlv.remove(s)
                subset = tuple(temp_shop + temp_dlv)
                subset_bundles.append(subset)
            
            # iterate through subset_bundles. if they are feasible, get the intersection of their candidates.
            first = 0
            for subset in subset_bundles:
                if subset in cand:
                    if first == 0: # initialize
                        new_cand['ff'] = cand[subset]['ff'].copy()
                        new_cand['bf'] = cand[subset]['bf'].copy()
                        new_cand['fb'] = cand[subset]['fb'].copy()
                        new_cand['bb'] = cand[subset]['bb'].copy()
                        first = 1
                    
                    new_cand['ff'] = new_cand['ff'] & cand[subset]['ff']
                    new_cand['bf'] = new_cand['bf'] & cand[subset]['bf']
                    new_cand['fb'] = new_cand['fb'] & cand[subset]['fb']
                    new_cand['bb'] = new_cand['bb'] & cand[subset]['bb']


            bundles[cur_depth].append(
                {
                    "seq" : comparison_dict[sorted_shop_seq]["seq"],
                    "candidate" : new_cand
                }
                )

        # 메모리 관리
        #bundles[cur_depth-1]['candidate'] = None
   
    del(bundles[cur_depth])

    for depth in bundles:
        bundles[depth] = [i['seq'] for i in bundles[depth]]

    total_cnt = 0
    for key in bundles:
        total_cnt += len(bundles[key])
        print(f"[{rider.type} {key}] {len(bundles[key])} bundles")
    print(f">>> Total {total_cnt} bundles of {rider.type}\n")

    all_bundles = []

    for depth in bundles:
        for shop_seq, dlv_seq in bundles[depth]:
            total_volume = get_total_volume(all_orders, shop_seq)
            total_dist = get_total_distance(dist_mat, shop_seq, dlv_seq, K)
            all_bundles.append(Bundle(all_orders, rider, shop_seq, dlv_seq, total_volume, total_dist))

    return all_bundles
