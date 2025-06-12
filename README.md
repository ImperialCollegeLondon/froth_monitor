# Froth monitor

---
Froth monitor is an interactive GUI application for analyzing froth videos in
real-time or offline. It allows users to draw **Regions of Interest (ROIs)**, track
**froth movement** using optical flow algorithm (more algorithms in the future), and
export detailed analysis results, including **delta pixels between frames, velocity data and timestamps**. It allows user to calibrate the **ratio of pixel to real distance** by ruler drawing, and define the **overflow direction of froths** by arrow drawing. It is also capable of **recording real-time video** from the camera.

## Installation and Usage

1. Clone the repository:

   ```bash
   git clone https://github.com/gyyyno1/Froth_monitor.git

2. Navigate to the project directory:

   ```bash
   cd your-repo

3. Install dependencies by poetry

   ```bash
   pipx install poetry
   poetry install
   ```

4. Run the application by poetry

   ```bash
   poetry run python -m froth_monitor
   ```

---

## Features

### Update 26th May 2025

A dynamic and interactive application designed to analyze and visualize froth
movement from video data using advanced image processing and data visualization
techniques.

### Features

#### 1. Arrow Direction Analysis

Draw, lock, and display an arrow indicating the direction of froth overflow.
Customizable and adjustable arrow direction for flexible analysis.

#### 2. Ruler drawing for calibration

Draw rulers on the video canvas to calibrate the distance between two points.
The distance between the two points is calculated and displayed on the canvas.

#### 2. Region of Interest (ROI) Drawing

Draw multiple ROIs on the video canvas.
Real-time movement analysis for each ROI.
Axis visualization (X and Y axes) within each ROI to track movement.

#### 3. Velocity Analysis

Real-time velocity analysis for each ROI.
Velocity data is displayed in a Cartesian coordinate system.
Velocity data is exported to an Excel file.

#### 4. Video Recording

This program is able to record the video stream directly from the camera. In case that the user want to re-analyze the video.

#### 5. Data Export

Export analysis results as Excel files.
Customizable file naming and export directory.
Separate sheets for each ROI in the Excel output.

#### 5. Replay and Reset

Save and end the current session, clearing ROIs and resetting the interface for a new analysis.

## Authors

- Mr Yiyang Guan - Department of Earth Science and Engineering, Imperial College London
