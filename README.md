# EEGApp

A PyQt5‑based desktop application for real‑time EEG streaming,
visualization, recording, and different mental states detection ---
using Bluetooth Low Energy (BLE).

## Overview

EEGApp lets you connect an EEG headset via BLE, visualize raw EEG
signals (time‑domain and FFT), record EEG data, and run a real‑time different mental states monitor.\
It supports user management, configurable signal processing (filtering,
downsampling, normalization), and modular pages.

## Features

-   BLE device discovery and connection\
-   Real‑time raw EEG and FFT visualization\
-   Configurable signal processing: band‑pass filter, notch filter,
    downsampling, normalization\
-   EEG data recording (CSV format)\
-   Real‑time different mental states detection\
-   Multi‑page GUI for user management, feature selection, calibration,
    monitoring

## Directory Structure

    EEGApp/
    ├── main.py
    ├── main_window.py
    ├── eeg_worker.py
    ├── style.qss
    ├── pages/
    ├── .gitignore
    └── README.md

## Installation

``` bash
git clone https://github.com/MirolabEEG/EEGApp.git
cd EEGApp
pip install -r requirements.txt
python main.py
```

## Requirements

-   Python 3.10+
-   PyQt5\
-   bleak\
-   numpy, scipy, matplotlib

