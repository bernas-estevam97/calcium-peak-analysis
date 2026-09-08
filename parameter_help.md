To pick the best parameters without knowing any underlying math or signal processing theory, all you need to do is **look at your trace** on **Tab 1** and **Tab 3** and follow this **5-step visual rule of thumb**:

---

### Step 1: Camera Acquisition ($\Delta t$ / FPS)
* **What it is:** The time interval between consecutive video frames.
* **How to set it:** You don't guess this—it comes directly from your microscope/camera setup:
  $$\Delta t = \frac{1000}{\text{FPS}} \quad \text{or} \quad \Delta t = \text{Frame Interval in ms}$$
  * *Example:* If your camera recorded at **100 FPS**, $\Delta t = 10.0\text{ ms}$. If recorded at **30 FPS**, $\Delta t = 33.3\text{ ms}$.

---

### Step 2: Baseline Window ($W_{\text{base}}$)
* **The Goal:** Make the baseline curve (the smooth trend line $F_0(t)$) hug the bottom of your valleys without "rising up" into your peaks.
* **Visual Rule of Thumb — *The 3-transient rule*:**
  1. Look at your raw trace and eyeball how wide **one single calcium spark/transient** is from when it begins rising until it returns to resting baseline (e.g., 80 frames).
  2. Set the **Baseline Window to 3 to 5 times that width** (e.g., $80 \times 4 \approx 320\text{ frames}$).
* **How to verify on the graph (Tab 1):**
  * ❌ **Window is too small:** The baseline line visibly bends upwards and tracks inside the peak. (This artificially cuts your peak height $\Delta F/F_0$ down).
  * ❌ **Window is too large:** The baseline fails to follow laser photobleaching or gradual recording drift.
  *  **Just right:** The baseline line stays flat underneath the peaks and only follows slow multi-second downward drift.

---

### Step 3: Peak Prominence ($P$)
* **The Goal:** Tell the detector how tall a peak must stand out above its local floor to count as a real biological event rather than sensor noise.
* **Visual Rule of Thumb — *The 3x Noise Floor rule*:**
  1. Switch your view to **$\Delta F/F_0$** on Tab 1 or Tab 3.
  2. Zoom in on a quiet stretch of flat baseline where no cells are firing, and observe the thickness of the camera "fuzz" (random noise).
     * *Example:* If the noise fluctuations wiggle by $\pm 0.02$, the noise floor height is $\approx 0.04$.
  3. Set **Prominence to 2.5× to 3× the noise thickness** (e.g., $\approx 0.10\text{ to }0.12$).
* **How to verify on the graph (Tab 3):**
  * ❌ **Prominence is too low:** Random jagged noise bumps get red inverted triangles $\triangledown$ on them.
  * ❌ **Prominence is too high:** Small but real biological transients don't get marked.
  *  **Just right:** Every true calcium transient has exactly one inverted triangle $\triangledown$ at its highest point, and zero triangles on flat baseline noise.

---

### Step 4: Minimum Distance ($D_{\text{min}}$)
* **The Goal:** Prevent a single noisy peak with multiple jagged crests from being counted as 2 or 3 separate events.
* **Visual Rule of Thumb — *Half the refractory gap*:**
  1. Look at the two peaks that fire **closest together** anywhere in your recording.
  2. Count or eyeball the number of frames between their centers.
  3. Set **Min Distance to slightly less than that gap** (e.g., if closest peaks are 60 frames apart, set Min Distance to $35\text{--}45\text{ frames}$).
  * *Typical default:* At 100 FPS, transients usually cannot re-fire faster than 300–500 ms, so **30 to 50 frames** is standard.

---

### Step 5: Savitzky-Golay Smoothing Window ($W_{\text{SG}}$)
* **The Goal:** Shave off high-frequency camera pixel noise so slopes and kinetic rise/decay times are clean and continuous.
* **Visual Rule of Thumb:**
  * Must always be an **odd integer** (e.g., 7, 9, 11, 15, 21).
  * Set it to roughly **10% to 15% of your peak's rise time duration**:
    * Fast kinetics / low frame rate (e.g., fast neurons or low FPS): **7 or 9**.
    * Moderate kinetics (e.g., cardiomyocytes at 100 FPS): **11 or 15**.
    * Slow kinetics (e.g., astrocytic calcium waves): **21 to 31**.
  * ❌ *Warning:* If you make it too large (e.g., 51), it will blunt the sharp peak tips and lower the measured $\Delta F/F_0$.

---

### Quick Cheat-Sheet by Cell Type

| Preparation / Signal Type | Typical FPS | Baseline Window | Prominence ($\Delta F/F_0$) | Min Distance | SG Window |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Cardiomyocytes** (hiPSC-CM / Ventricular) | 50 – 100 FPS | 300 – 500 frames | 0.08 – 0.15 | 40 – 60 frames | 11 – 15 |
| **Cortical Neurons** (Action potential bursts) | 30 – 100 FPS | 150 – 300 frames | 0.10 – 0.20 | 20 – 40 frames | 7 – 11 |
| **Astrocytes / Calcium Waves** (Slow signals) | 10 – 30 FPS | 500 – 1000 frames | 0.05 – 0.10 | 80 – 120 frames | 21 – 31 |

---