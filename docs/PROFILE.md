# Category 24 reference spectrum

The optional profile follows **MIL-STD-810H with Change 1, 18 May 2022**, Method 514.8, Annex E, Figure 514.8E-1, Category 24. The figure is printed on page **514.8E-3**, PDF page **457** in the inspected document.

| Frequency | Density |
|---:|---:|
| 20 Hz | 0.040 g²/Hz |
| 1000 Hz | 0.040 g²/Hz |
| 2000 Hz | 0.010 g²/Hz |

The nominal −6 dB/octave segment is reconstructed as a fourfold PSD decrease per octave, or f⁻². Thus the endpoint is 0.010 g²/Hz. Log-log interpolation gives an input of **sqrt(59.2) = 7.6942 g RMS**, consistent with the figure's rounded **7.7 g**. The specified duration is **one hour per axis**.

Annex E's preceding page excludes minimum-integrity testing from qualification use. The profile is not an aircraft-specific operational environment and is not a substitute for environmental tailoring. The recorded application is numerical Z-axis screening only; recording duration in the configuration does not constitute exposure testing or calculate fatigue life.

Sources: [official DLA record](https://quicksearch.dla.mil/qsDocDetails.aspx?ident_number=35978), [inspected copy of the original DoD document](https://cvgstrategy.com/wp-content/uploads/2023/04/MIL-STD-810H-change-1.pdf). The profile JSON records the revision, page, source URL and inspected document SHA-256.

```bash
vibequal run examples/enclosure.json \
  --profile examples/profiles/mil_std_810h_cat24.json --out runs/category24
```

`--profile` replaces the configuration's PSD explicitly; it does not alter geometry, mass, mode count or damping. The main demonstration retains its illustrative profile so earlier band-edge comparisons remain reproducible. No DO-160 profile is reproduced.
