import math

a = float(input())
b = float(input())

diag_cm = math.sqrt(a ** 2 + b ** 2)

diag_inch = diag_cm / 2.54
print(f"{diag_inch:.1f}")