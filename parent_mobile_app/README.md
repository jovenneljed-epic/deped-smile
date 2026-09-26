# DepEd Project S.M.I.L.E. - Standalone Parent Mobile App

Official Mobile Companion App for **Don Montano Central Integrated School** parents and guardians. Enables real-time monitoring of school gate arrivals & departures, push alerts, school announcements, and the interactive school events & activities calendar.

---

## 📱 Features

1. **Gate Safety & Live Timeline:**
   - Real-time campus presence indicator (`INSIDE CAMPUS`, `SAFELY EXITED`, `AWAITING ARRIVAL`).
   - Gate scan timestamps with security gate ID and verification method (AI Face Biometrics / DepEd QR Badge).
2. **Notification Center & Alerts:**
   - Real-time alerts on gate scans with audible entry/exit chimes and phone vibration.
   - Emergency school announcements and weather suspension bulletins.
3. **School Bulletins & DepEd Memos:**
   - Categorized announcements (Weather, DepEd Orders, PTA Assemblies, Clinic Advisories).
4. **Events & School Calendar:**
   - Interactive timeline of upcoming school activities with category tags (Academic, Sports, PTA, Cultural, Brigada).
   - 1-click **Add to Calendar (.ics)** file generation for native device calendars (Google Calendar / Apple Calendar).
5. **Guardian Pick-Up Pass & Student Profile:**
   - High-contrast digital Pick-Up Pass QR code for presenting to gate security guards.
   - Student academic section, adviser name, and digital excuse letter filing.

---

## 🚀 Building the Android APK

### Option A: Direct WebAPK (Zero-Install on Phone)
1. Open `https://deped-smile.vercel.app/mobile` in Chrome on any Android phone.
2. Tap the **"Install App"** banner or tap Chrome menu $\rightarrow$ **"Install App"**.
3. Android OS compiles and installs a native WebAPK directly onto your device launcher.

### Option B: Local Android Studio Build (Debug / Release APK)
```bash
# 1. Navigate to the mobile app folder
cd parent_mobile_app

# 2. Install dependencies
npm install

# 3. Add Android platform via Capacitor
npx cap add android

# 4. Sync web assets
npx cap sync android

# 5. Open in Android Studio
npx cap open android
```
- In Android Studio, go to **Build** $\rightarrow$ **Build Bundle(s) / APK(s)** $\rightarrow$ **Build APK(s)**.
- Output APK location: `android/app/build/outputs/apk/debug/app-debug.apk`.

### Option C: Command-Line Gradle Build
```bash
cd parent_mobile_app/android
./gradlew assembleDebug
```

---

## 🍏 iOS Deployment (iPhone & iPad)

### Option A: Apple Native Home Screen App (No Developer Account Needed)
1. Open `https://deped-smile.vercel.app/mobile` in Safari on iPhone.
2. Tap the blue **Share** button (`⬆`) at the bottom of Safari.
3. Scroll down and tap **"Add to Home Screen"** $\rightarrow$ tap **"Add"**.
4. The app installs on the iPhone home screen with the official DepEd icon and supports native Web Push Notifications (iOS 16.4+).

### Option B: Xcode Native Build (For TestFlight & App Store)
```bash
cd parent_mobile_app
npm install
npx cap add ios
npx cap sync ios
npx cap open ios
```
- Requires a Mac with macOS and Xcode installed.
- Select your Development Team and target device or simulator to run.
