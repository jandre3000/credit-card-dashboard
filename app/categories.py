"""Transaction auto-categorization rules.
Maps merchant keywords to spending categories. Order matters — first match wins."""

# (keywords_in_uppercase_description, category)
RULES = [
    # Grocery
    (["FRESHCO", "FOOD BASICS", "LOBLAWS", "NO FRILLS", "SOBEYS", "METRO",
      "FOODLAND", "ZEHRS", "FARM BOY", "COSTCO WHOLESALE"], "Grocery"),

    # Dining / Delivery
    (["UBER EATS", "DOORDASH", "SKIP THE DISHES", "PIZZA", "RESTAURANT",
      "CAFE", "COFFEE", "SECOND CUP", "TIM HORTON", "STARBUCKS",
      "MCDONALD", "BURGER", "SUSHI", "INDULGE ICE CREAM", "COBS BREAD",
      "BAKERY", "BRUNCH", "DINER", "GRILL", "PIZZERIA", "ELAN PIZZA",
      "RISE TO FRIES", "JTM CAKE", "THE HATCHET", "LCBO", "BEER STORE",
      "WINE RACK"], "Dining & Drinks"),

    # Gas / Transit
    (["PETRO-CANADA", "SHELL", "ESSO", "ULTRAMAR", "CANADIAN TIRE GAS",
      "HUSKY", "CO-OP GAS", "WOLF ENERGY", "MR CONVENIENCE", "BB FUELS",
      "UBER TRIP", "TAXI", "TRANSIT", "GO TRANSIT", "PRESTO"], "Gas & Transit"),

    # Streaming / Subscriptions
    (["SPOTIFY", "NETFLIX", "APPLE.COM/BILL", "AMAZON.CA PRIME",
      "AMAZON CHANNELS", "YOUTUBE PREMIUM", "DISNEY+", "CRAVE",
      "PATREON", "CURSOR", "ANTHROPIC", "OPENAI", "LINK.COM",
      "OPEN SOURCE COLLECTIVE", "BACKBLAZE", "AMAZON WEB SERVICES"], "Subscriptions"),

    # Shopping / Retail
    (["AMZN MKTP", "AMAZON.CA", "WAL-MART", "WALMART", "CANADIAN TIRE",
      "DOLLARAMA", "SHERIDAN NURSERIES", "HOME HARDWARE", "HOME DEPOT",
      "IKEA", "INDIGO", "WINNERS", "MARSHALLS", "NIKE", "H&M",
      "HM.COM", "YETI"], "Shopping"),

    # Health / Pharmacy
    (["SHOPPERS DRUG MART", "REXALL", "PHARMACY", "MEDICAL", "DENTAL",
      "OPTICAL"], "Health"),

    # Telecom
    (["TELUS", "ROGERS", "BELL", "LUCKY MOBILE", "FIDO", "KOODO",
      "FREED MOBILE"], "Telecom"),

    # Home / Services
    (["MAID IN HEAVEN", "CLEANING", "HYDRO", "ENBRIDGE", "WATER",
      "INSURANCE"], "Home & Services"),

    # Charitable / Donations
    (["CANADIANCANCERSOCIETY", "PLAN CANADA", "DONATION", "CHARITY",
      "UNICEF", "RED CROSS"], "Donations"),

    # Travel
    (["AIR CANADA", "WESTJET", "AIRBNB", "BOOKING.COM", "HOTEL",
      "SEATS.AERO", "AEROPLAN"], "Travel"),

    # Education / Kids
    (["ACT*CITYCAMBRIDGEREC", "SCHOOL", "UNIVERSITY", "COURSE"], "Kids & Education"),

    # Auto / Insurance
    (["CAA", "AUTOMOBILE", "CAR WASH", "PARKING"], "Auto"),

    # Gifts
    (["GIFT", "FLOWERS"], "Gifts"),
]


def categorize(description: str) -> str:
    """Auto-assign a spending category based on merchant keywords."""
    desc_upper = description.upper()
    for keywords, category in RULES:
        for kw in keywords:
            if kw in desc_upper:
                return category
    return "Other"