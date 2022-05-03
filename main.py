import fnmatch
import json
import os
import numpy
import random

from deap import base, creator, tools

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


# tworzenie folderów
def make_directories(pathname):
    try:
        os.makedirs(os.path.split(pathname)[0])
    except:
        pass


# tworzenie plików json z plików tekstwoych z danych dostępnych na stronie Salomona
def text2json():
    def __distance(customer1, customer2):
        return ((customer1['coordinates']['x'] - customer2['coordinates']['x']) ** 2 + (
                customer1['coordinates']['y'] - customer2['coordinates']['y']) ** 2) ** 0.5

    text_data_dir = os.path.join(BASE_DIR, 'META6_229875', 'data', 'text')
    json_data_dir = os.path.join(BASE_DIR, 'META6_229875', 'data', 'json')
    for text_file in map(lambda text_filename: os.path.join(text_data_dir, text_filename),
                         fnmatch.filter(os.listdir(text_data_dir), '*.txt')):
        json_data = {}
        # Count the number of lines in the file to customize the number of customers
        size = sum(1 for _ in open(text_file))
        with open(text_file) as f:
            for lineNum, line in enumerate(f, start=1):
                if lineNum in [2, 3, 4, 6, 7, 8, 9]:
                    pass
                elif lineNum == 1:
                    json_data['instance_name'] = line.strip()
                elif lineNum == 5:
                    values = line.strip().split()
                    json_data['max_vehicle_number'] = int(values[0])
                    json_data['vehicle_capacity'] = float(values[1])
                    try:
                        gotdata = values[2]
                    except IndexError:
                        gotdata = False
                    if gotdata:
                        json_data['max_light_vehicle_number'] = int(values[2])
                        json_data['light_vehicle_capacity'] = float(values[3])
                        json_data['light_vehicle_range'] = float(values[4])
                    else:
                        pass
                elif lineNum == 10:
                    values = line.strip().split()
                    json_data['deport'] = {
                        'coordinates': {
                            'x': float(values[1]),
                            'y': float(values[2]),
                        },
                        'demand': float(values[3]),
                        'ready_time': float(values[4]),
                        'due_time': float(values[5]),
                        'service_time': float(values[6]),
                    }
                else:
                    # <Custom number>, <X coordinate>, <Y coordinate>, <Demand>, <Ready time>, <Due date>, <Service time>
                    values = line.strip().split()
                    json_data['customer_%s' % values[0]] = {
                        'coordinates': {
                            'x': float(values[1]),
                            'y': float(values[2]),
                        },
                        'demand': float(values[3]),
                        'ready_time': float(values[4]),
                        'due_time': float(values[5]),
                        'service_time': float(values[6]),
                    }
        # jest dokładnie 9 linijek przed danymi klientów
        number_of_customers = size - 9
        customers = ['deport'] + ['customer_%d' % x for x in range(1, number_of_customers)]
        json_data['distance_matrix'] = [
            [__distance(json_data[customer1], json_data[customer2]) for customer1 in customers]
            for customer2 in customers]
        json_filename = '%s.json' % json_data['instance_name']
        json_pathname = os.path.join(json_data_dir, json_filename)
        print('Write to file: %s' % json_pathname)
        make_directories(pathname=json_pathname)
        with open(json_pathname, 'w') as f:
            json.dump(json_data, f, sort_keys=True, indent=4, separators=(',', ': '))


def individual2route(individual, instance, speed=1.0):
    route = []
    vehicle_capacity = instance['vehicle_capacity']
    deport_due_time = instance['deport']['due_time']
    # inicjalizacja sub-route
    sub_route = []
    vehicle_load = 0
    elapsed_time = 0
    last_customerID = 0
    for customerID in individual:
        # update ładowność pojazdu
        demand = instance['customer_%d' % customerID]['demand']
        updated_vehicle_load = vehicle_load + demand
        # update elapsed-time (czas jaki upłynął)
        service_time = instance['customer_%d' % customerID]['service_time']
        return_time = instance['distance_matrix'][customerID][0] * speed
        updated_elapsed_time = elapsed_time + (
                instance['distance_matrix'][last_customerID][customerID] * speed) + service_time + return_time
        # walidacja ładowność pojazdu i czasu
        if (updated_vehicle_load <= vehicle_capacity) and (updated_elapsed_time <= deport_due_time):
            # dodaj do bieżącej sub-route
            sub_route.append(customerID)
            vehicle_load = updated_vehicle_load
            elapsed_time = updated_elapsed_time - return_time
        else:
            # zapisz bieżącą sub-route
            route.append(sub_route)
            # Initialize a new sub-route and add to it
            sub_route = [customerID]
            vehicle_load = demand
            elapsed_time = (instance['distance_matrix'][0][customerID] * speed) + service_time
        # update ID ostatnio odwiedzonego klienta
        last_customerID = customerID
    if sub_route:
        # jeśli sub-route nie jest pusta zapisz ją do ścieżki głównej (route)
        route.append(sub_route)
    return route


def eval_vrptw(individual, instance, cost_of_unit, cost_of_waiting, cost_of_delay, speed=1):
    route = individual2route(individual, instance, speed)
    total_cost = 0
    for subRoute in route:
        sub_route_time_cost = 0
        sub_route_distance = 0
        elapsed_time = 0
        last_customerID = 0
        for customerID in subRoute:
            # oblicz dystans
            distance = instance['distance_matrix'][last_customerID][customerID] * speed
            # update sub-route distance
            sub_route_distance = sub_route_distance + distance
            # oblicz koszt związany z czasem
            arrival_time = elapsed_time + distance
            time_cost = cost_of_waiting * max(instance['customer_%d' % customerID]['ready_time'] - arrival_time,
                                              0) + cost_of_delay * max(
                arrival_time - instance['customer_%d' % customerID]['due_time'], 0)
            # update koszt związany z czasem dla danej sub-route
            sub_route_time_cost = sub_route_time_cost + time_cost
            # update elapsed-time
            elapsed_time = arrival_time + instance['customer_%d' % customerID]['service_time']
            # update ID ostatnio odwiedzonego klienta
            last_customerID = customerID
        # oblicz koszt związany z transportem
        sub_route_distance = sub_route_distance + (instance['distance_matrix'][last_customerID][0] * speed)
        sub_route_tran_cost = cost_of_unit * sub_route_distance
        # koszt związany z czasem
        sub_route_cost = sub_route_time_cost + sub_route_tran_cost
        # koszt sumarycznie
        total_cost = total_cost + sub_route_cost
    fitness = 1.0 / total_cost
    return fitness,


def crossover_partially_matched(ind1, ind2):
    # Partially Matched crossover
    size = min(len(ind1), len(ind2))
    p1, p2 = [0] * size, [0] * size

    # zainicjuj pozycję każdego wskaźnika w poszczególnych osobnikach
    for i in range(size):
        p1[ind1[i] - 1] = i
        p2[ind2[i] - 1] = i
    # wybór punktów krzyżowania
    point1 = random.randint(0, size)
    point2 = random.randint(0, size - 1)
    if point2 >= point1:
        point2 += 1
    else:  # wymiana punktów krzyżowania
        point1, point2 = point2, point1

    # krzyżowanie pomiędzy punktami
    for i in range(point1, point2):

        temp1 = ind1[i]
        temp2 = ind2[i]

        ind1[i], ind1[p1[temp2 - 1]] = temp2, temp1
        ind2[i], ind2[p2[temp1 - 1]] = temp1, temp2

        p1[temp1 - 1], p1[temp2 - 1] = p1[temp2 - 1], p1[temp1 - 1]
        p2[temp1 - 1], p2[temp2 - 1] = p2[temp2 - 1], p2[temp1 - 1]

    return ind1, ind2


def mutation_inverse_indexes(individual):
    start, stop = sorted(random.sample(range(len(individual)), 2))
    individual = individual[:start] + individual[stop:start - 1:-1] + individual[stop + 1:]
    return individual,


def printRoute(route, merge=False):
    route_str = '0'
    sub_route_count = 0
    for sub_route in route:
        sub_route_count += 1
        sub_route_str = '0'
        for customer_id in sub_route:
            sub_route_str = f'{sub_route_str} - {customer_id}'
            route_str = f'{route_str} - {customer_id}'
        sub_route_str = f'{sub_route_str} - 0'
        if not merge:
            print(f'  Vehicle {sub_route_count}\'s route: {sub_route_str}')
        route_str = f'{route_str} - 0'
    if merge:
        print(route_str)


def genetic_algorithm_for_vrptw(instance_name, individual_size, population_size, crossover_rate, mutation_rate,
                                number_of_generations, cost_of_unit=1.0, cost_of_waiting=0.0,
                                cost_of_delay=0.0):
    json_data_dir = os.path.join(BASE_DIR, 'META6_229875', 'data', 'json')
    json_file = os.path.join(json_data_dir, '%s.json' % instance_name)
    with open(json_file) as f:
        instance = json.load(f)
    creator.create('FitnessMax', base.Fitness, weights=(1.0,))
    creator.create('Individual', list, fitness=creator.FitnessMax)
    toolbox = base.Toolbox()
    # Attribute generator
    toolbox.register('indexes', random.sample, range(1, individual_size + 1), individual_size)
    # Structure initializers
    toolbox.register('individual', tools.initIterate, creator.Individual, toolbox.indexes)
    toolbox.register('population', tools.initRepeat, list, toolbox.individual)
    # Operator registering
    toolbox.register('evaluate', eval_vrptw, instance=instance, cost_of_unit=cost_of_unit,
                     cost_of_waiting=cost_of_waiting,
                     cost_of_delay=cost_of_delay)
    toolbox.register('select', tools.selRoulette)
    toolbox.register('mate', crossover_partially_matched)
    toolbox.register('mutate', mutation_inverse_indexes)
    # inicjalizacja populacji
    pop = toolbox.population(n=population_size)
    print('Start of evolution for %s' % instance_name)
    # ewaluacja populacji
    fitness = list(toolbox.map(toolbox.evaluate, pop))
    for ind, fit in zip(pop, fitness):
        ind.fitness.values = fit

    # rozpoczęcie procesu ewolucji
    for g in range(number_of_generations):
        # selekcja następnej generacji
        # selekcja elitarna - najlepszy osobnik, zabezpieczony przed mutacją i krzyżowaniem
        elite = tools.selBest(pop, 1)
        # selekcja top 10% wszystkich dzieci
        # selekcja ruletkowa pozostałych 90% dzieci
        offspring = tools.selBest(pop, int(numpy.ceil(len(pop) * 0.1)))
        offspring_roulette = toolbox.select(pop, int(numpy.floor(len(pop) * 0.9)) - 1)
        offspring.extend(offspring_roulette)
        # klonowanie wybranych indywidułów do następnej generacji
        offspring = list(toolbox.map(toolbox.clone, offspring))
        # krzyżowanie i mutacja
        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < crossover_rate:
                toolbox.mate(child1, child2)
                del child1.fitness.values
                del child2.fitness.values
        for mutant in offspring:
            if random.random() < mutation_rate:
                toolbox.mutate(mutant)
                del mutant.fitness.values
        # ewaluacja indywidułów z niepoprawnym fitnessem
        invalid_individual = [ind for ind in offspring if not ind.fitness.valid]
        fitness = toolbox.map(toolbox.evaluate, invalid_individual)
        for ind, fit in zip(invalid_individual, fitness):
            ind.fitness.values = fit
        # zamiana całej populacji na nową utworzoną z potomków
        offspring.extend(elite)
        pop[:] = offspring

    print('End of (successful) evolution')
    best_individual = tools.selBest(pop, 1)[0]
    print('Best individual: %s' % best_individual)
    print('Fitness: %s' % best_individual.fitness.values[0])
    printRoute(individual2route(best_individual, instance))
    if cost_of_waiting == cost_of_delay == 0 and cost_of_unit == 1.0:
        print('Distance: %s' % (1 / best_individual.fitness.values[0]))
    else:
        print('Total cost: %s' % (1 / best_individual.fitness.values[0]))


if __name__ == '__main__':
    # text2json()
    genetic_algorithm_for_vrptw('C101', 100, 100, 0.9, 0.05, 200)
    genetic_algorithm_for_vrptw('C102', 100, 100, 0.9, 0.05, 250)
    genetic_algorithm_for_vrptw('C103', 100, 100, 0.9, 0.05, 250)

    genetic_algorithm_for_vrptw('R101', 100, 100, 0.8, 0.01, 250)
    genetic_algorithm_for_vrptw('R102', 100, 100, 0.8, 0.01, 250)
    genetic_algorithm_for_vrptw('R103', 100, 100, 0.8, 0.01, 250)

    genetic_algorithm_for_vrptw('RC101', 100, 100, 0.9, 0.06, 300)
    genetic_algorithm_for_vrptw('RC102', 100, 100, 0.9, 0.06, 300)
    genetic_algorithm_for_vrptw('RC103', 100, 100, 0.9, 0.06, 300)

    genetic_algorithm_for_vrptw('C201', 100, 100, 0.9, 0.03, 250)
    genetic_algorithm_for_vrptw('C202', 100, 100, 0.9, 0.01, 250)
    genetic_algorithm_for_vrptw('C203', 100, 100, 0.8, 0.01, 250)

    genetic_algorithm_for_vrptw('R201', 100, 100, 0.8, 0.01, 250)
    genetic_algorithm_for_vrptw('R202', 100, 100, 0.8, 0.01, 250)
    genetic_algorithm_for_vrptw('R203', 100, 100, 0.8, 0.01, 250)

    genetic_algorithm_for_vrptw('RC201', 100, 100, 0.9, 0.01, 250)
    genetic_algorithm_for_vrptw('RC202', 100, 100, 0.9, 0.01, 300)
    genetic_algorithm_for_vrptw('RC203', 100, 100, 0.9, 0.01, 300)
