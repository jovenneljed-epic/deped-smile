# DepEd Project S.M.I.L.E. - Expo Mobile App (Expo Go & Standalone APK)

Official native mobile companion application for **DepEd Project S.M.I.L.E.** (Smart Monitoring & Integrated Learner Enrollment System) for Don Montano Central Integrated School.

Built with **React Native** and **Expo**, ready for **Expo Go** live testing and **EAS Build** standalone APK compilation.

---

## 📱 Features

- 🟢 **Live Campus Arrival / Dismissal Status:** Real-time indicator (`INSIDE CAMPUS`, `SAFELY EXITED`, or `AWAITING ARRIVAL`).
- 🔔 **Instant Gate Alerts & Native Vibration:** Wakes phone and vibrates using native device hardware when student scans at the school gate.
- 👨‍👩‍👧 **Multi-Child / Sibling Switcher:** Allows parents to switch between multiple enrolled children in 1 tap.
- 📋 **Today's Attendance Timeline:** Detailed timestamps, gate kiosk devices, and entry/exit verification methods.
- 📝 **Excuse Letter Filing:** Submit excuse notes directly to class advisers with reason, date, and doctor's explanation.
- ⚠️ **Official School Bulletins:** Emergency class suspensions, DepEd memorandums, and campus alerts.
- 📅 **DepEd School Calendar:** Quarterly exams, Brigada Eskwela, Parent-Teacher conferences.
- ⚡ **Cloud Connected:** Seamlessly synchronized with live production backend at `https://deped-smile.vercel.app`.

---

## 🚀 Option 1: Run Instantly in Expo Go (No APK Installation Needed)

This is the fastest way to run the real native app on any physical Android phone or iPhone within 60 seconds:

### Step 1: Install Expo Go on Your Mobile Phone
- **Android:** Download [Expo Go on Google Play Store](https://play.google.com/store/apps/details?id=host.exp.exponent)
- **iPhone:** Download [Expo Go on Apple App Store](https://apps.apple.com/app/expo-go/id982107779)

### Step 2: Start the Expo Development Server
In your computer's terminal:
```bash
cd deped_smile_expo
npm install
npx expo start --tunnel
```
*(Using `--tunnel` allows your phone to connect over cellular data or different Wi-Fi networks without firewall issues).*

### Step 3: Scan QR Code with Phone
- **On Android:** Open the **Expo Go** app and tap **"Scan QR Code"**.
- **On iPhone:** Open the default **Camera** app and point it at the terminal QR code, then tap the Expo notification.

The native DepEd S.M.I.L.E. Parent App will load immediately on your mobile phone!

---

## 📦 Option 2: Build a Standalone Android APK (`.apk` File)

To generate a standalone `.apk` file that you can install directly on any Android phone (without needing Expo Go or a computer running):

### Step 1: Install EAS CLI
```bash
npm install -g eas-cli
```

### Step 2: Log in to your free Expo account
```bash
npx eas login
```
*(If you don't have an account, create a free account at [expo.dev](https://expo.dev/signup)).*

### Step 3: Trigger APK Build
Run this single command:
```bash
npx eas build -p android --profile preview
```

### Step 4: Download and Install
- EAS will build your APK in the Expo cloud for free.
- Once finished (takes ~5–10 minutes), terminal displays a direct download link and QR code for the `.apk` file.
- Open the download link on your Android phone and tap **Install**!

---

## ⚙️ Configuration & Cloud Endpoints

The app is pre-configured to connect to:
- **Production Backend:** `https://deped-smile.vercel.app`
- **Default Demonstration LRN:** `152008250007` (Juan Dela Cruz)

To change the backend server or learner LRN:
1. Tap the **⚙️ (Settings)** icon in the top right corner of the mobile app.
2. Enter your server URL or custom LRN.
3. Tap **Save & Connect**.
