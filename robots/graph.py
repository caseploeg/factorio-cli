import matplotlib.pyplot as plt
import time
import client
import ast

# Production data over time
t = 0
production_data = [] 
flag = False
while True:
    prod_data = client.production() 
    data = ast.literal_eval(prod_data)
    prod_dict = dict()
    prod_dict['time'] = t 
    for item in data:
        prod_dict[item[0]] = item[1]
    production_data.append(prod_dict)

    # Get the list of items from the first data point
    if production_data:
        items = list(production_data[0].keys())[1:]

        # Create a plot for each item
        for item in items:
            # Get the production data for the item over time
            item_data = [point[item] for point in production_data]

            # Create a line plot for the item
            plt.plot([point['time'] for point in production_data], item_data, label=item)

        # Set the title and axis labels
        plt.title('Production Over Time')
        plt.xlabel('Time')
        plt.ylabel('Production')

        # Add a legend to the plot
        if not flag:
            plt.legend()
            flag = True

        # Display the plot
        plt.draw()
    plt.pause(5)
    t += 5
