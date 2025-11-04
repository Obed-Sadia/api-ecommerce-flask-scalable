TAUX_IMPOSITION = {
    'QC': 0.15,
    'ON': 0.13,
    'AB': 0.05,
    'BC': 0.12,
    'NS': 0.14
}

def calculate_shipping(weight):
    if weight <= 500:
        return 5
    elif weight <= 2000:
        return 10
    return 25