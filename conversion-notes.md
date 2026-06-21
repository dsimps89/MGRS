# Conversion Notes

## Python concepts converted

- MGRS Program / Finder variants: sun-angle latitude estimator, landmark distance estimate, longitude delta estimate, coordinate display.
- MGRS with image: replaced Folium output with a lightweight concept map panel.
- Infantry Program variants: terrain score, weather score, friendly/reference unit values, resource tracking, and distance calculation.
- Tactical Ops Advisor: combined terrain mode and tactical review into a single dashboard.
- Military Program: high-level dashboard recommendation logic converted into a transparent scoring panel.

## Technical changes

- Python console inputs became HTML forms.
- NumPy/math logic became vanilla JavaScript.
- JSON/file persistence became browser `localStorage`.
- Matplotlib/Folium visualization became CSS cards, a grid matrix, and printable reports.

## Accuracy limitations

MGRS conversion is represented as an approximate MGRS-style coordinate string, not a certified geodesy library output. For production, integrate a validated MGRS JavaScript library and test against known coordinates.
