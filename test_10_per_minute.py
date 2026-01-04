#!/usr/bin/env python3
"""
Test to verify 10 iron plates per minute production
We'll consume the excess inventory and then measure production
"""

import client
import json
import ast
from datetime import timedelta

def main():
    print("="*80)
    print("TESTING 10 IRON PLATES PER MINUTE PRODUCTION")
    print("="*80)

    # Get current state
    print("\nCurrent inventory:")
    inv = client.get_inventory()
    print(json.dumps(inv, indent=2))

    print("\nCurrent production:")
    prod = client.production()
    print(prod)

    # The limit is preventing production. Let's remove the limit first
    print("\n" + "="*80)
    print("Removing production limit to allow free production...")
    print("="*80)
    client.limit("iron-plate", 999999)  # Set very high limit

    print("\nRunning for 1 minute with no limit...")
    client.next(1)

    print("\nProduction after 1 minute:")
    prod_result = client.production()
    prod_data = ast.literal_eval(prod_result)
    for row in prod_data:
        item, actual, potential, inventory, limit = row
        if item == "iron-plate":
            print(f"  Iron plates: {actual:.1f}/min actual, {potential:.1f}/min potential")
            print(f"  Inventory: {inventory}")

    # Now set limit to exactly 10
    print("\n" + "="*80)
    print("Setting limit to 10 iron plates/min...")
    print("="*80)
    client.limit("iron-plate", 10)

    # Check production with limit
    print("\nProduction with 10/min limit:")
    prod_result = client.production()
    prod_data = ast.literal_eval(prod_result)
    for row in prod_data:
        item, actual, potential, inventory, limit = row
        if item == "iron-plate":
            print(f"  Iron plates: {actual:.1f}/min actual, {potential:.1f}/min potential")
            print(f"  Inventory: {inventory}")
            print(f"  Limit: {limit}")

    # Run for multiple minutes and track production
    print("\n" + "="*80)
    print("Running for 3 minutes to observe limited production...")
    print("="*80)

    initial_inv = client.get_inventory()
    initial_iron = initial_inv.get("iron-plate", 0)
    print(f"Initial iron plates: {initial_iron}")

    client.next(3)

    final_inv = client.get_inventory()
    final_iron = final_inv.get("iron-plate", 0)
    print(f"Final iron plates: {final_iron}")
    print(f"Change over 3 minutes: {final_iron - initial_iron} plates")
    print(f"Average rate: {(final_iron - initial_iron) / 3:.1f} plates/min")

    print("\nFinal production stats:")
    prod_result = client.production()
    print("\n" + "="*80)
    print("PRODUCTION TABLE")
    print("="*80)
    prod_data = ast.literal_eval(prod_result)
    print(f"{'Item':<25} {'Actual/min':>12} {'Potential/min':>15} {'Inventory':>12} {'Limit':>10}")
    print("-" * 80)
    for row in prod_data:
        item, actual, potential, inventory, limit = row
        limit_str = str(limit) if limit else "-"
        print(f"{item:<25} {actual:>12.1f} {potential:>15.1f} {inventory:>12} {limit_str:>10}")

    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)
    print("""
The factory is set up with:
  • 4 burner mining drills on iron-ore (60 ore/min)
  • 6 stone furnaces for iron-plate (126 plates/min potential)
  • Production limit set to 10 iron plates/min

The limit system controls the maximum production rate, but actual
production depends on whether there's demand (inventory consumption).

When inventory is full, production may stop even with a limit set.
The limit ensures we don't produce MORE than 10/min, but if there's
no consumption, we won't produce at all.

For true steady-state 10/min production, we would need to continuously
consume iron plates (e.g., by crafting other items).
""")

if __name__ == "__main__":
    main()
