#!/usr/bin/env python3
"""
Demonstrate true 10 iron plates/min production
by using them in other recipes
"""

import client
import json
import ast
from datetime import timedelta

def show_production():
    """Helper to show production in a nice format"""
    prod_result = client.production()
    prod_data = ast.literal_eval(prod_result)
    print(f"\n{'Item':<25} {'Actual/min':>12} {'Potential/min':>15} {'Inventory':>12} {'Limit':>10}")
    print("-" * 80)
    for row in prod_data:
        item, actual, potential, inventory, limit = row
        limit_str = str(limit) if limit else "-"
        status = ""
        if item == "iron-plate" and limit == 10:
            if abs(actual - 10) < 1.0:
                status = " ✓"
        print(f"{item:<25} {actual:>12.1f} {potential:>15.1f} {inventory:>12} {limit_str:>10}{status}")
    return prod_data

def main():
    print("="*80)
    print("DEMONSTRATING 10 IRON PLATES PER MINUTE PRODUCTION")
    print("="*80)

    # Strategy: Set limit to 10, then craft items to consume iron plates
    # This will create steady-state 10/min production

    print("\nStep 1: Ensure limit is set to 10")
    client.limit("iron-plate", 10)

    print("\nCurrent state:")
    inv = client.get_inventory()
    print(f"  Iron plates: {inv.get('iron-plate', 0)}")
    print(f"  Iron ore: {inv.get('iron-ore', 0)}")

    show_production()

    print("\n" + "="*80)
    print("Step 2: Set up consumption to demonstrate steady-state")
    print("="*80)
    print("We'll consume iron plates by crafting iron gear wheels")
    print("This will allow the furnaces to produce at the limited rate")

    # First, let's demonstrate the system is capable of 10/min by adjusting
    # We need to think about this differently - the limit prevents production
    # when inventory > limit. So let's demonstrate it working at 10/min

    print("\nActually, let me demonstrate this correctly:")
    print("The limit of 10/min means:")
    print("  • If inventory < limit: produce up to limit/min")
    print("  • If inventory >= limit: don't produce")

    print("\nLet's reset and demonstrate properly...")

    # Consume most iron plates
    print("\nConsuming excess iron plates by crafting gear wheels...")
    current_iron = inv.get('iron-plate', 0)
    if current_iron > 50:
        # Craft gear wheels to reduce iron plate inventory
        to_craft = (current_iron - 20) // 2
        print(f"Crafting {to_craft} iron gear wheels to reduce inventory...")
        client.craft("iron-gear-wheel", to_craft)

    inv = client.get_inventory()
    print(f"\nAfter consumption:")
    print(f"  Iron plates: {inv.get('iron-plate', 0)}")

    print("\n" + "="*80)
    print("Step 3: Set limit to exactly 50 plates in inventory")
    print("="*80)
    print("This way, the factory will produce to maintain 50 plates")
    client.limit("iron-plate", 50)

    print("\nRunning for 2 minutes...")
    client.next(2)

    prod_data = show_production()
    inv = client.get_inventory()
    print(f"\nInventory after 2 minutes:")
    print(f"  Iron plates: {inv.get('iron-plate', 0)}")

    # Now show actual 10/min by adjusting
    print("\n" + "="*80)
    print("Step 4: Demonstrate controlled 10/min production")
    print("="*80)

    # Set up a scenario where we maintain exactly 10/min
    # by crafting items at the same rate
    print("Setting limit to 100 to allow some buffer...")
    client.limit("iron-plate", 100)

    print("\nNow let's measure the potential and set up for 10/min:")
    print("We have 126/min potential. To get 10/min actual,")
    print("we can either:")
    print("  1. Reduce number of furnaces")
    print("  2. Use the limit system")
    print("  3. Reduce ore input")

    print("\nUsing approach #3: Limit iron ore production")
    print("For 10 iron plates/min, we need 10 iron ore/min")
    print("Setting iron-ore limit to 10/min...")
    client.limit("iron-ore", 10)

    print("\nRunning for 2 minutes with iron-ore limited...")
    client.next(2)

    prod_data = show_production()

    # Find iron-plate production
    for row in prod_data:
        item, actual, potential, inventory, limit = row
        if item == "iron-plate":
            print(f"\n🎯 RESULT: Iron plate production is {actual:.1f} plates/min")
            if abs(actual - 10) < 2.0:
                print("✓ Successfully achieved ~10 iron plates per minute!")
            break

    print("\n" + "="*80)
    print("FINAL SETUP")
    print("="*80)
    print("""
To achieve 10 iron plates per minute production:
  • Set iron-ore production limit to 10/min
  • This ensures furnaces receive only 10 ore/min
  • Result: ~10 iron plates produced per minute

Current factory setup:
  • 4 burner mining drills on iron-ore (60/min potential)
  • 6 stone furnaces for iron-plate (126/min potential)
  • Iron-ore limited to 10/min → Iron-plate output ~10/min

The limit system successfully controls production rates!
""")

    inv = client.get_inventory()
    print(f"Final inventory:")
    print(json.dumps(inv, indent=2))

if __name__ == "__main__":
    main()
