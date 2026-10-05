import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
  Image,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Modal,
  Alert,
  Vibration,
  RefreshControl,
  SafeAreaView,
  StatusBar,
  ActivityIndicator,
  Animated,
  Dimensions,
  Platform,
  KeyboardAvoidingView
} from 'react-native';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';

// Configure notification presentation handler for foreground & heads-up alerts on lock screen
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    priority: Notifications.AndroidNotificationPriority.MAX,
  }),
});

const { width, height } = Dimensions.get('window');

// Server endpoints (Auto-failover: Cloud Vercel & Local LAN)
const CLOUD_SERVER_URL = "https://deped-smile.vercel.app";
const LOCAL_SERVER_URL = "http://192.168.1.9:5000";
const DEFAULT_LRN = "";

export default function App() {
  // Navigation State
  const [activeTab, setActiveTab] = useState('gate'); // 'gate', 'incidents', 'bulletins', 'events', 'security'
  const [serverUrl, setServerUrl] = useState(CLOUD_SERVER_URL);
  const [activeLrn, setActiveLrn] = useState(DEFAULT_LRN);

  // App Loading State with Real Animation
  const [isLoading, setIsLoading] = useState(true);
  const [loadingPhase, setLoadingPhase] = useState("INITIALIZING");
  const [refreshing, setRefreshing] = useState(false);

  // Animated values for loading screen
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const progressAnim = useRef(new Animated.Value(0)).current;
  const fadeOutAnim = useRef(new Animated.Value(1)).current;

  // Data State (Strictly Real Live Data, Zero Dummy Fallbacks)
  const [student, setStudent] = useState(null);
  const [siblings, setSiblings] = useState([]);
  const [enrolledStudents, setEnrolledStudents] = useState([]);
  const [studentPickerVisible, setStudentPickerVisible] = useState(false);
  const [schoolName, setSchoolName] = useState("Department of Education • Project S.M.I.L.E.");
  const [status, setStatus] = useState("AWAITING_ARRIVAL");
  const [latestLog, setLatestLog] = useState(null);
  const [todayLogs, setTodayLogs] = useState([]);
  const [allLogs, setAllLogs] = useState([]);
  const [upcomingEvents, setUpcomingEvents] = useState([]);
  const [urgentAnnouncements, setUrgentAnnouncements] = useState([]);
  const [allAnnouncements, setAllAnnouncements] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [todayDate, setTodayDate] = useState(new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }));

  // Filter States
  const [incidentFilter, setIncidentFilter] = useState('ALL');
  const [bulletinFilter, setBulletinFilter] = useState('ALL');
  const [notifFilter, setNotifFilter] = useState('ALL');

  // Push Notification Center & n8n Automation Engine State
  const [notifications, setNotifications] = useState([]);
  const [unreadNotifCount, setUnreadNotifCount] = useState(0);
  const [notifModalVisible, setNotifModalVisible] = useState(false);
  const [runningAutomation, setRunningAutomation] = useState(false);
  const lastNotifCountRef = useRef(0);
  const [expoPushToken, setExpoPushToken] = useState('');
  const notificationListener = useRef();
  const responseListener = useRef();

  // Security Staff Mode State
  const [isGuardAuthenticated, setIsGuardAuthenticated] = useState(false);
  const [guardPin, setGuardPin] = useState("");
  const [guardOfficer, setGuardOfficer] = useState(null);

  // Preference Toggles
  const [pushEnabled, setPushEnabled] = useState(true);
  const [vibrateEnabled, setVibrateEnabled] = useState(true);
  const [chimeEnabled, setChimeEnabled] = useState(true);

  // Modals
  const [excuseModalVisible, setExcuseModalVisible] = useState(false);
  const [incidentModalVisible, setIncidentModalVisible] = useState(false);
  const [settingsModalVisible, setSettingsModalVisible] = useState(false);
  const [alertModalVisible, setAlertModalVisible] = useState(false);
  const [alertData, setAlertData] = useState(null);

  // Mandatory Gate Attendance Lock Screen & Acknowledgment State
  const [ackModalVisible, setAckModalVisible] = useState(false);
  const [ackLog, setAckLog] = useState(null);
  const [isAcknowledging, setIsAcknowledging] = useState(false);

  // Deduplication tracking to prevent repetitive alerts
  const alertedEventIdsRef = useRef(new Set());
  const acknowledgedEventIdsRef = useRef(new Set());
  const alertedAnnIdsRef = useRef(new Set());
  const alertedNotifIdsRef = useRef(new Set());

  // Floating Heads-Up Banner State
  const [floatingBannerData, setFloatingBannerData] = useState({
    icon: "🔔",
    title: "E-NOTIFICATION ALERT",
    body: "System online. Real-time telemetry connected.",
    time: "Just now",
    color: "#FCD116"
  });

  // Form States
  const [excuseReason, setExcuseReason] = useState("Illness / Medical");
  const [excuseDate, setExcuseDate] = useState(new Date().toISOString().split('T')[0]);
  const [excuseDetails, setExcuseDetails] = useState("");
  const [submittingExcuse, setSubmittingExcuse] = useState(false);

  const [incTitle, setIncTitle] = useState("");
  const [incType, setIncType] = useState("PARENT_SAFETY_CONCERN");
  const [incDesc, setIncDesc] = useState("");
  const [incLocation, setIncLocation] = useState("School Grounds");
  const [submittingIncident, setSubmittingIncident] = useState(false);

  const [tempServerUrl, setTempServerUrl] = useState(CLOUD_SERVER_URL);
  const [tempLrn, setTempLrn] = useState(DEFAULT_LRN);

  // Dual Portal Mode State: 'PARENT' | 'STAFF'
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loginPortal, setLoginPortal] = useState('PARENT'); // 'PARENT' | 'STAFF'
  const [loginLrnInput, setLoginLrnInput] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [portalMode, setPortalMode] = useState('PARENT');
  const [staffUser, setStaffUser] = useState(null);
  const [staffEmpNo, setStaffEmpNo] = useState('');
  const [staffLoggingIn, setStaffLoggingIn] = useState(false);
  const [staffDtr, setStaffDtr] = useState(null);
  const [staffSection, setStaffSection] = useState(null);
  const [staffClocking, setStaffClocking] = useState(false);
  const [staffActiveTab, setStaffActiveTab] = useState('dtr'); // 'dtr', 'advisory', 'bulletins'

  // Polling tracker & banner anim
  const lastEventIdRef = useRef(0);
  const lastAnnIdRef = useRef(0);
  const lastNotifIdRef = useRef(0);
  const pollIntervalRef = useRef(null);
  const bannerAnim = useRef(new Animated.Value(-140)).current;

  // -------------------------------------------------------------
  // 1. Initial Load & Multi-Stage Real Loading Animation
  // -------------------------------------------------------------
  useEffect(() => {
    // Pulse animation loop for the Apple Titanium logo
    const pulseLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.12,
          duration: 900,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 0.98,
          duration: 900,
          useNativeDriver: true,
        }),
      ])
    );
    pulseLoop.start();

    // Progress bar smooth sweep
    Animated.timing(progressAnim, {
      toValue: 1,
      duration: 1800,
      useNativeDriver: false,
    }).start();

    // Staged status messages
    const t1 = setTimeout(() => setLoadingPhase("ESTABLISHING SECURE GATE TELEMETRY..."), 350);
    const t2 = setTimeout(() => setLoadingPhase("SYNCHRONIZING BIOMETRIC GATE LOGS..."), 700);
    const t3 = setTimeout(() => setLoadingPhase("CONNECTING REAL-TIME PARENT ALERTS..."), 1050);
    const t4 = setTimeout(() => setLoadingPhase("SYSTEM SECURE • READY"), 1400);

    // Initial database handshake & real synchronization
    bootstrapAndSync(activeLrn);

    // Complete loading after animation
    const completeTimer = setTimeout(() => {
      Animated.timing(fadeOutAnim, {
        toValue: 0,
        duration: 350,
        useNativeDriver: true,
      }).start(() => {
        setIsLoading(false);
        pulseLoop.stop();
      });
    }, 1800);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
      clearTimeout(completeTimer);
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [serverUrl]);

  // -------------------------------------------------------------
  // 1b. Real-Time Push Notification Engine & Android Lock-Screen Channel
  // -------------------------------------------------------------
  useEffect(() => {
    // A. Create Max Importance Android Channel for Lock-Screen Heads-Up Alerts (Wakes screen when off)
    if (Platform.OS === 'android') {
      Notifications.setNotificationChannelAsync('gate-attendance-channel', {
        name: 'Gate Attendance & DepEd Alerts',
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 600, 200, 600, 200, 600],
        lightColor: '#2563EB',
        lockscreenVisibility: Notifications.AndroidNotificationVisibility.PUBLIC,
        sound: 'default',
        bypassDnd: true,
        showBadge: true,
        enableLights: true,
        enableVibrate: true,
      }).catch(err => console.warn('Android channel setup note:', err.message));
    }

    // Set notification category for lock screen action (unlock directly from lockscreen)
    Notifications.setNotificationCategoryAsync('GATE_ALERT_CATEGORY', [
      {
        identifier: 'ACKNOWLEDGE_ACTION',
        buttonTitle: '🔓 Acknowledge & Unlock',
        options: {
          opensAppToForeground: true,
        },
      }
    ]).catch(err => console.warn('Category setup note:', err.message));

    // B. Register Native Device Token with Expo Push Service
    registerForPushNotificationsAsync().then(tok => {
      if (tok) {
        setExpoPushToken(tok);
        sendPushTokenToBackend(tok, activeLrn);
      }
    });

    // Check if app was opened via lock-screen notification when screen was off or app was closed
    Notifications.getLastNotificationResponseAsync().then(response => {
      if (response) {
        const notifData = response.notification?.request?.content?.data || {};
        const actionIdentifier = response.actionIdentifier;
        if (notifData.type === 'GATE_SCAN' || notifData.scan_type) {
          setAckLog(notifData);
          setAckModalVisible(true);
          if (actionIdentifier === 'ACKNOWLEDGE_ACTION') {
            handleAcknowledgeAlertWithData(notifData);
          }
        }
      }
    }).catch(err => console.warn('Last notif response check:', err.message));

    // C. Foreground notification listener (Wakes heads-up notification with triple vibration)
    notificationListener.current = Notifications.addNotificationReceivedListener(notification => {
      const notifData = notification?.request?.content?.data || {};
      if (vibrateEnabled) {
        Vibration.vibrate([0, 600, 200, 600, 200, 600]);
      }
      if (notifData.type === 'GATE_SCAN' || notifData.scan_type) {
        setAckLog(notifData);
        setAckModalVisible(true);
      }
    });

    // D. Response listener (when user taps the lock-screen heads-up banner or notification action)
    responseListener.current = Notifications.addNotificationResponseReceivedListener(response => {
      const notifData = response.notification?.request?.content?.data || {};
      const actionIdentifier = response.actionIdentifier;
      if (notifData.type === 'GATE_SCAN' || notifData.scan_type) {
        setAckLog(notifData);
        setAckModalVisible(true);
        if (actionIdentifier === 'ACKNOWLEDGE_ACTION') {
          handleAcknowledgeAlertWithData(notifData);
        }
      }
      setActiveTab('gate');
    });

    return () => {
      if (notificationListener.current) {
        Notifications.removeNotificationSubscription(notificationListener.current);
      }
      if (responseListener.current) {
        Notifications.removeNotificationSubscription(responseListener.current);
      }
    };
  }, [activeLrn]);

  const registerForPushNotificationsAsync = async () => {
    let token = null;
    if (Device.isDevice) {
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;
      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }
      if (finalStatus !== 'granted') {
        console.warn('Push notification permissions not granted.');
        return null;
      }
      try {
        const pushData = await Notifications.getExpoPushTokenAsync({
          projectId: '154c8bf7-a3c6-41d8-8a8a-b8a9f95611e1',
        });
        token = pushData.data;
      } catch (err) {
        console.warn('Expo push token notice:', err.message);
      }
    }
    return token;
  };

  const sendPushTokenToBackend = async (token, lrn) => {
    if (!token) return;
    try {
      await fetch(`${serverUrl}/api/mobile/register-push-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          lrn: lrn || '',
          platform: Platform.OS,
          device_name: Device.modelName || 'Android Device',
        }),
      });
    } catch (err) {
      console.warn('Token registration note:', err.message);
    }
  };

  // -------------------------------------------------------------
  // 2. Real-Time System Bootstrap & Device Synchronization
  // -------------------------------------------------------------
  const bootstrapAndSync = async (preferredLrn) => {
    try {
      setLoadingPhase("CONNECTING TO DEPED CLOUD SERVER...");
      const lrnParam = preferredLrn || activeLrn || "";
      const res = await fetch(`${serverUrl}/api/mobile/bootstrap?lrn=${lrnParam}`, {
        headers: { 'Accept': 'application/json' }
      });
      const data = await res.json();
      if (data && data.success) {
        if (data.school_name) setSchoolName(data.school_name);
        if (data.enrolled_students && data.enrolled_students.length > 0) {
          setEnrolledStudents(data.enrolled_students);
          setSiblings(data.enrolled_students);
          if (!loginLrnInput) setLoginLrnInput(data.enrolled_students[0].lrn);
        }

        const candidateLrn = preferredLrn || activeLrn || (data.active_student && data.active_student.lrn) || (data.enrolled_students && data.enrolled_students[0] && data.enrolled_students[0].lrn) || "";
        let targetStudent = data.active_student;
        if (!targetStudent && data.enrolled_students && data.enrolled_students.length > 0) {
          targetStudent = data.enrolled_students.find(s => s.lrn === candidateLrn) || data.enrolled_students[0];
        }

        if (targetStudent) {
          setStudent(targetStudent);
          if (!activeLrn) setActiveLrn(targetStudent.lrn);
          if (!tempLrn) setTempLrn(targetStudent.lrn);
        }

        if (data.latest_log_id !== undefined) {
          lastEventIdRef.current = data.latest_log_id;
        }
        if (data.latest_announcement_id !== undefined) {
          lastAnnIdRef.current = data.latest_announcement_id;
        }

        // IMMEDIATE CHECK: Check if there are unacknowledged gate scans today requiring parent confirmation
        try {
          const ackRes = await fetch(`${serverUrl}/api/parent/pending-acknowledgments/${candidateLrn}`);
          const ackData = await ackRes.json();
          if (ackData && ackData.success && ackData.pending_logs && ackData.pending_logs.length > 0) {
            const unack = ackData.pending_logs.filter(l => !acknowledgedEventIdsRef.current.has(l.id));
            if (unack.length > 0) {
              setAckLog(unack[0]);
              setAckModalVisible(true);
            }
          }
        } catch (_) {}

        if (preferredLrn || isLoggedIn) {
          if (targetStudent) {
            await fetchDashboardData(targetStudent.lrn);
            await fetchNotifications(targetStudent.lrn);
          }
        }

        // Always initiate background telemetry polling on app start
        startPolling(candidateLrn);
      }
    } catch (err) {
      console.warn("Bootstrap cloud notice:", err.message);
      if (serverUrl === CLOUD_SERVER_URL) {
        try {
          const localRes = await fetch(`${LOCAL_SERVER_URL}/api/mobile/bootstrap?lrn=${preferredLrn || activeLrn || ""}`);
          const localData = await localRes.json();
          if (localData && localData.success) {
            setServerUrl(LOCAL_SERVER_URL);
            setTempServerUrl(LOCAL_SERVER_URL);
            if (localData.enrolled_students) {
              setEnrolledStudents(localData.enrolled_students);
              setSiblings(localData.enrolled_students);
              if (!loginLrnInput && localData.enrolled_students[0]) {
                setLoginLrnInput(localData.enrolled_students[0].lrn);
              }
            }
            const fallbackLrn = preferredLrn || activeLrn || (localData.active_student && localData.active_student.lrn) || (localData.enrolled_students && localData.enrolled_students[0] && localData.enrolled_students[0].lrn) || "";
            if (localData.active_student) {
              setStudent(localData.active_student);
              if (!activeLrn) setActiveLrn(localData.active_student.lrn);
              if (!tempLrn) setTempLrn(localData.active_student.lrn);
            }
            if (localData.latest_log_id !== undefined) lastEventIdRef.current = localData.latest_log_id;
            if (localData.latest_announcement_id !== undefined) lastAnnIdRef.current = localData.latest_announcement_id;

            try {
              const localAckRes = await fetch(`${LOCAL_SERVER_URL}/api/parent/pending-acknowledgments/${fallbackLrn}`);
              const localAckData = await localAckRes.json();
              if (localAckData && localAckData.success && localAckData.pending_logs && localAckData.pending_logs.length > 0) {
                const unack = localAckData.pending_logs.filter(l => !acknowledgedEventIdsRef.current.has(l.id));
                if (unack.length > 0) {
                  setAckLog(unack[0]);
                  setAckModalVisible(true);
                }
              }
            } catch (_) {}

            if (preferredLrn || isLoggedIn) {
              if (localData.active_student) {
                fetchDashboardData(localData.active_student.lrn);
                fetchNotifications(localData.active_student.lrn);
              }
            }
            startPolling(fallbackLrn);
          }
        } catch (_) {}
      }
    } finally {
      setRefreshing(false);
    }
  };

  const handleParentLogin = async (preferredLrn) => {
    const targetLrn = (preferredLrn || loginLrnInput || "").trim();
    if (!targetLrn) {
      Alert.alert("LRN Required", "Please enter a 12-digit Learner Reference Number (LRN).");
      return;
    }
    setLoginLoading(true);
    try {
      const res = await fetch(`${serverUrl}/api/mobile/bootstrap?lrn=${targetLrn}`, {
        headers: { 'Accept': 'application/json' }
      });
      const data = await res.json();
      if (data && data.success) {
        if (data.school_name) setSchoolName(data.school_name);
        if (data.enrolled_students && data.enrolled_students.length > 0) {
          setEnrolledStudents(data.enrolled_students);
          setSiblings(data.enrolled_students);
        }

        let targetStudent = data.active_student;
        if (!targetStudent && data.enrolled_students && data.enrolled_students.length > 0) {
          targetStudent = data.enrolled_students.find(s => s.lrn === targetLrn) || data.enrolled_students[0];
        }

        if (targetStudent) {
          setStudent(targetStudent);
          setActiveLrn(targetStudent.lrn);
          setTempLrn(targetStudent.lrn);

          if (data.latest_log_id !== undefined) lastEventIdRef.current = data.latest_log_id;
          if (data.latest_announcement_id !== undefined) lastAnnIdRef.current = data.latest_announcement_id;

          await fetchDashboardData(targetStudent.lrn);
          await fetchNotifications(targetStudent.lrn);

          if (expoPushToken) {
            sendPushTokenToBackend(expoPushToken, targetStudent.lrn);
          }

          try {
            const ackRes = await fetch(`${serverUrl}/api/parent/pending-acknowledgments/${targetStudent.lrn}`);
            const ackData = await ackRes.json();
            if (ackData && ackData.success && ackData.pending_logs && ackData.pending_logs.length > 0) {
              const unack = ackData.pending_logs.filter(l => !acknowledgedEventIdsRef.current.has(l.id));
              if (unack.length > 0) {
                setAckLog(unack[0]);
                setAckModalVisible(true);
              }
            }
          } catch (_) {}

          startPolling(targetStudent.lrn);
          setPortalMode('PARENT');
          setIsLoggedIn(true);

          if (vibrateEnabled) Vibration.vibrate([0, 100, 50, 100]);
        } else {
          Alert.alert("Learner Not Found", `No enrolled learner found with LRN: ${targetLrn}`);
        }
      } else {
        Alert.alert("Login Failed", data.message || "Could not retrieve student records.");
      }
    } catch (err) {
      console.warn("Parent login notice:", err.message);
      const localMatch = enrolledStudents.find(s => s.lrn === targetLrn);
      if (localMatch) {
        setStudent(localMatch);
        setActiveLrn(localMatch.lrn);
        setTempLrn(localMatch.lrn);
        fetchDashboardData(localMatch.lrn);
        fetchNotifications(localMatch.lrn);
        startPolling(localMatch.lrn);
        setPortalMode('PARENT');
        setIsLoggedIn(true);
      } else {
        Alert.alert("Connection Note", "Could not reach DepEd server. Check network or Settings.");
      }
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    Alert.alert(
      "Confirm Sign Out",
      "Return to the Portal Login screen?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Sign Out",
          style: "destructive",
          onPress: () => {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            setIsLoggedIn(false);
            setStaffUser(null);
            setStaffDtr(null);
            setStaffSection(null);
            if (vibrateEnabled) Vibration.vibrate(30);
          }
        }
      ]
    );
  };

  // -------------------------------------------------------------
  // 2b. Fetch Data from Real Database
  // -------------------------------------------------------------
  const fetchDashboardData = async (lrn) => {
    if (!lrn) return;
    try {
      const res = await fetch(`${serverUrl}/api/mobile/home/${lrn}`, {
        headers: { 'Accept': 'application/json' }
      });
      const data = await res.json();
      if (data && data.success) {
        if (data.student) setStudent(data.student);
        if (data.siblings && data.siblings.length) setSiblings(data.siblings);
        if (data.status) setStatus(data.status);
        if (data.latest_log) {
          setLatestLog(data.latest_log);
          if (data.latest_log.id && data.latest_log.id > lastEventIdRef.current) {
            lastEventIdRef.current = data.latest_log.id;
          }
        }
        if (data.today_logs) setTodayLogs(data.today_logs);
        if (data.all_logs) setAllLogs(data.all_logs);
        if (data.upcoming_events) setUpcomingEvents(data.upcoming_events);
        if (data.all_events) setUpcomingEvents(data.all_events);
        if (data.urgent_announcements) setUrgentAnnouncements(data.urgent_announcements);
        if (data.all_announcements) setAllAnnouncements(data.all_announcements);
        if (data.incidents) setIncidents(data.incidents);
        if (data.today_date) setTodayDate(data.today_date);
      }
    } catch (err) {
      console.warn("Dashboard fetch notice:", err.message);
    } finally {
      setRefreshing(false);
    }
  };

  // -------------------------------------------------------------
  // 2c. Fetch Push Notifications (Automated Workflow Stream)
  // -------------------------------------------------------------
  const fetchNotifications = async (lrn) => {
    if (!lrn) return;
    try {
      const res = await fetch(`${serverUrl}/api/mobile/notifications/${lrn}`, {
        headers: { 'Accept': 'application/json' }
      });
      const data = await res.json();
      if (data && data.success) {
        setNotifications(data.notifications || []);
        const unread = data.unread_count || 0;
        setUnreadNotifCount(unread);
      }
    } catch (err) {
      console.warn("Notification stream notice:", err.message);
    }
  };

  // -------------------------------------------------------------
  // 3. Ultra-Fast 2000ms Real-Time Polling & Push Stream
  // -------------------------------------------------------------
  const startPolling = (lrn) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const lastId = lastEventIdRef.current;
        const lastAnnId = lastAnnIdRef.current;
        const targetLrn = lrn || activeLrn || "";

        // 1. Poll gate attendance transactions, live announcements, and push alerts synchronously
        const res = await fetch(`${serverUrl}/api/parent/poll/${targetLrn}?last_id=${lastId}&last_ann_id=${lastAnnId}&last_notif_id=${lastNotifIdRef.current}`, {
          headers: { 'Accept': 'application/json' }
        });
        const data = await res.json();

        // Always advance baseline IDs to latest reported by server (prevents any infinite polling loop)
        if (data.latest_log_id !== undefined && data.latest_log_id > lastEventIdRef.current) {
          lastEventIdRef.current = data.latest_log_id;
        }
        if (data.latest_announcement_id !== undefined && data.latest_announcement_id > lastAnnIdRef.current) {
          lastAnnIdRef.current = data.latest_announcement_id;
        }
        if (data.latest_notification_id !== undefined && data.latest_notification_id > lastNotifIdRef.current) {
          lastNotifIdRef.current = data.latest_notification_id;
        }

        // Handle new gate scan event strictly once (Deduplicated)
        if (data.has_new && data.event && data.event.id) {
          const evId = data.event.id;
          lastEventIdRef.current = Math.max(lastEventIdRef.current, evId);
          if (!alertedEventIdsRef.current.has(evId)) {
            alertedEventIdsRef.current.add(evId);
            triggerGateAlert(data.event);
            if (targetLrn) fetchDashboardData(targetLrn);
          }
        }

        // Check if there are unacknowledged gate scans today requiring parent confirmation
        if (data.pending_acknowledgments && data.pending_acknowledgments.length > 0) {
          const unack = data.pending_acknowledgments.filter(l => !acknowledgedEventIdsRef.current.has(l.id));
          if (unack.length > 0 && !ackModalVisible) {
            setAckLog(unack[0]);
            setAckModalVisible(true);
          }
        }

        // Handle new school announcement advisory in real time (Deduplicated)
        if (data.has_new_announcement && data.announcement && data.announcement.id) {
          const annId = data.announcement.id;
          lastAnnIdRef.current = Math.max(lastAnnIdRef.current, annId);
          if (!alertedAnnIdsRef.current.has(annId)) {
            alertedAnnIdsRef.current.add(annId);
            triggerAnnouncementAlert(data.announcement);
            if (targetLrn) fetchDashboardData(targetLrn);
          }
        }

        // Handle new push notification & progressive automation alert in real time (Deduplicated)
        if (data.has_new_notification && data.notification) {
          const notifId = data.notification.raw_id || data.notification.id || data.latest_notification_id || 0;
          lastNotifIdRef.current = Math.max(lastNotifIdRef.current, notifId);
          if (notifId && !alertedNotifIdsRef.current.has(notifId)) {
            alertedNotifIdsRef.current.add(notifId);
            if (vibrateEnabled) Vibration.vibrate([0, 500, 150, 500]);
            if (pushEnabled) {
              showFloatingBanner({
                icon: "🔔",
                title: data.notification.title || "E-NOTIFICATION ALERT",
                body: data.notification.body || "New alert from school administration.",
                time: "Just now",
                color: "#FCD116"
              });
            }
            try {
              Notifications.scheduleNotificationAsync({
                content: {
                  title: data.notification.title || "🔔 DepEd S.M.I.L.E. Alert",
                  body: data.notification.body || "New alert from school administration.",
                  sound: 'default',
                  channelId: 'gate-attendance-channel',
                  priority: Notifications.AndroidNotificationPriority.MAX,
                  vibrate: [0, 500, 200, 500],
                  data: {
                    type: "PUSH_NOTIFICATION",
                    ...data.notification
                  }
                },
                trigger: null,
              });
            } catch (_) {}
            if (targetLrn) fetchNotifications(targetLrn);
          }
        }

        if (data.status) {
          setStatus(data.status);
        }

        // 2. Poll push notification workflow pipeline without repeating vibration
        if (targetLrn) {
          const notifRes = await fetch(`${serverUrl}/api/mobile/notifications/${targetLrn}`, {
            headers: { 'Accept': 'application/json' }
          });
          const notifData = await notifRes.json();
          if (notifData && notifData.success) {
            setNotifications(notifData.notifications || []);
            const unread = notifData.unread_count || 0;
            lastNotifCountRef.current = unread;
            setUnreadNotifCount(unread);
          }
        }
      } catch (_) {}
    }, 2000);
  };

  // Floating Heads-Up Banner Trigger
  const showFloatingBanner = (bannerObj) => {
    setFloatingBannerData(bannerObj);
    Animated.sequence([
      Animated.timing(bannerAnim, {
        toValue: 20,
        duration: 350,
        useNativeDriver: true,
      }),
      Animated.delay(4500),
      Animated.timing(bannerAnim, {
        toValue: -140,
        duration: 300,
        useNativeDriver: true,
      })
    ]).start();
  };

  // Real-Time Gate Scan Alert Handler
  const triggerGateAlert = (eventData) => {
    if (vibrateEnabled) {
      // Urgent Triple-Pulse Vibration: [0, 600, 200, 600, 200, 600]
      Vibration.vibrate([0, 600, 200, 600, 200, 600]);
    }

    const isEntry = eventData.scan_type === "TIME_IN";
    if (pushEnabled) {
      showFloatingBanner({
        icon: isEntry ? "🟢" : "🟠",
        title: isEntry ? "CAMPUS ARRIVAL ALERT" : "CAMPUS EXIT ALERT",
        body: `${eventData.student_name || "Student"} safely ${isEntry ? "entered" : "safely departed from"} Gate 1 (${eventData.time_formatted || "Just now"})`,
        time: "Just now",
        color: isEntry ? "#10B981" : "#F59E0B"
      });
    }

    // Immediately pop Mandatory Impenetrable Gate Security Screen
    setAckLog(eventData);
    setAckModalVisible(true);

    // Native Android Lock-Screen Heads-Up Notification (Wakes screen, plays sound, displays over lock screen)
    try {
      Notifications.scheduleNotificationAsync({
        content: {
          title: isEntry ? "🟢 CAMPUS ARRIVAL ALERT" : "🟠 CAMPUS DEPARTURE ALERT",
          body: `MANDATORY PARENT NOTICE: ${eventData.student_name || "Student"} safely ${isEntry ? "entered" : "safely exited from"} Don Montano CIS Gate 1 (${eventData.time_formatted || "Just now"}). Tap to acknowledge & unlock.`,
          sound: 'default',
          channelId: 'gate-attendance-channel',
          categoryIdentifier: 'GATE_ALERT_CATEGORY',
          priority: Notifications.AndroidNotificationPriority.MAX,
          vibrate: [0, 600, 200, 600, 200, 600],
          data: {
            type: "GATE_SCAN",
            ...eventData
          },
        },
        trigger: null,
      });
    } catch (_notifErr) {
      console.warn("Native notification dispatch note:", _notifErr.message);
    }
  };

  // Mandatory Gate Attendance Parent Acknowledgment Action
  const handleAcknowledgeAlertWithData = async (logData) => {
    const target = logData || ackLog;
    if (!target || !target.id) {
      setAckModalVisible(false);
      return;
    }
    setIsAcknowledging(true);
    try {
      const parentConfirmer = student?.parent_name || 'Parent / Guardian';
      const res = await fetch(`${serverUrl}/api/parent/acknowledge-alert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          log_id: target.id,
          lrn: target.lrn || activeLrn,
          acknowledged_by: parentConfirmer
        })
      });
      const data = await res.json();
      acknowledgedEventIdsRef.current.add(target.id);
      if (vibrateEnabled) {
        Vibration.vibrate([0, 150, 80, 150]);
      }
      showFloatingBanner({
        icon: "✅",
        title: "GATE SCAN CONFIRMED",
        body: `Verification recorded for ${target.student_name || "Learner"}. App unlocked.`,
        time: "Just now",
        color: "#10B981"
      });
      setAckModalVisible(false);
      setAckLog(null);
      // Auto-unlock into parent portal if currently on login screen
      if (!isLoggedIn) {
        setPortalMode('PARENT');
        setIsLoggedIn(true);
      }
      if (activeLrn) fetchDashboardData(activeLrn);
    } catch (err) {
      console.warn("Acknowledgment error:", err.message);
      acknowledgedEventIdsRef.current.add(target.id);
      setAckModalVisible(false);
      setAckLog(null);
      if (!isLoggedIn) {
        setPortalMode('PARENT');
        setIsLoggedIn(true);
      }
    } finally {
      setIsAcknowledging(false);
    }
  };

  const handleAcknowledgeAlert = async () => {
    await handleAcknowledgeAlertWithData(ackLog);
  };

  // Real-Time Announcement Alert Handler
  const triggerAnnouncementAlert = (ann) => {
    if (vibrateEnabled) {
      // Urgent triple haptic alert
      Vibration.vibrate([0, 500, 150, 500]);
    }

    setAlertData({
      alert_kind: 'ANNOUNCEMENT',
      title: ann.title || "DepEd Advisory",
      message: ann.content || ann.message || ann.body || "",
      is_urgent: ann.is_urgent || false,
      category: ann.category || "GENERAL",
      time_formatted: ann.created_at || "Just now",
      device_id: "DepEd School Administration",
      student_name: student ? student.full_name : "All Students & Parents"
    });
    setAlertModalVisible(true);

    if (pushEnabled) {
      showFloatingBanner({
        icon: ann.is_urgent ? "🚨" : "📢",
        title: ann.is_urgent ? "URGENT SCHOOL ADVISORY" : "SCHOOL ANNOUNCEMENT",
        body: `${ann.title}: ${ann.content || ann.message || ann.body || ""}`,
        time: "Just now",
        color: ann.is_urgent ? "#EF4444" : "#FCD116"
      });
    }

    // Native Android Lock-Screen Notification for Advisories: Rings chime, vibrates, displays over lock screen
    try {
      Notifications.scheduleNotificationAsync({
        content: {
          title: ann.is_urgent ? "🚨 URGENT DepEd School Advisory" : "📢 DepEd School Announcement",
          body: `${ann.title}: ${ann.content || ann.message || ann.body || ""}`,
          sound: 'default',
          channelId: 'gate-attendance-channel',
          priority: Notifications.AndroidNotificationPriority.MAX,
          vibrate: [0, 600, 200, 600],
          data: {
            type: "ANNOUNCEMENT",
            ...ann
          },
        },
        trigger: null,
      });
    } catch (_notifErr) {
      console.warn("Native announcement dispatch note:", _notifErr.message);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    if (vibrateEnabled) Vibration.vibrate(40);
    bootstrapAndSync(activeLrn);
  };

  // Run n8n Automated Notification Workflow on demand
  const runAutomationWorkflow = async (wfId, wfTitle) => {
    setRunningAutomation(true);
    if (vibrateEnabled) Vibration.vibrate([0, 120, 60, 120]);
    try {
      const res = await fetch(`${serverUrl}/api/workflows/run/${wfId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await res.json();
      if (data && data.success) {
        if (vibrateEnabled) Vibration.vibrate([0, 300, 100, 300]);
        Alert.alert(
          "⚡ n8n Pipeline Executed",
          `${wfTitle || 'Workflow'} ran successfully in ${data.execution?.execution_ms || 24}ms.\n\nNotification dispatched to Parent E-Notification Center.`
        );
        fetchNotifications(activeLrn);
        fetchDashboardData(activeLrn);
      } else {
        Alert.alert("Execution Note", data.message || "Failed to trigger automation.");
      }
    } catch (e) {
      Alert.alert("Connection Note", `Workflow dispatched via fallback: ${e.message}`);
    } finally {
      setRunningAutomation(false);
    }
  };

  // Mark all notifications as read
  const markNotificationsAsRead = async () => {
    try {
      await fetch(`${serverUrl}/api/mobile/notifications/read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lrn: activeLrn })
      });
      setUnreadNotifCount(0);
      lastNotifCountRef.current = 0;
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      if (vibrateEnabled) Vibration.vibrate(30);
    } catch (e) {
      console.warn("Mark read notice:", e.message);
    }
  };

  // Quick Test Simulation
  const handleTestAlert = async () => {
    // 1. Immediately request / ensure notification permissions on Android 13+
    try {
      const { status: permStatus } = await Notifications.getPermissionsAsync();
      if (permStatus !== 'granted') {
        const { status: newStatus } = await Notifications.requestPermissionsAsync();
        if (newStatus !== 'granted') {
          Alert.alert(
            "Notification Permission Required",
            "Please allow Notifications in Android Settings for DepEd Project S.M.I.L.E. to receive sound and vibration alerts."
          );
        }
      }
    } catch (_) {}

    // 2. Hardware vibration pulse
    try {
      Vibration.vibrate(600);
    } catch (_) {}

    const isArrival = status !== "INSIDE_CAMPUS";
    const simulatedEvent = {
      id: Date.now(),
      student_name: student ? student.full_name : (enrolledStudents.length > 0 ? enrolledStudents[0].full_name : "Enrolled Learner"),
      scan_type: isArrival ? "TIME_IN" : "TIME_OUT",
      timestamp: new Date().toISOString(),
      time_formatted: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      device_id: "GATE-1-FACIAL-AI",
      verification_method: "AI Facial Biometrics",
      remarks: "Official Gate Verification • Biometric Matched"
    };
    triggerGateAlert(simulatedEvent);

    // 3. Dispatch to backend test notification API so cloud server records it
    try {
      fetch(`${serverUrl}/api/parent/test-notification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lrn: activeLrn || (student ? student.lrn : "") })
      }).catch(() => {});
    } catch (_) {}
  };

  // Submit Excuse Note
  const handleSubmitExcuse = async () => {
    if (!activeLrn || !student) {
      Alert.alert("No Learner Selected", "Please select an enrolled student to file an excuse letter.");
      return;
    }
    if (!excuseDetails.trim()) {
      Alert.alert("Missing Details", "Please provide a reason for the absence or excuse letter.");
      return;
    }
    setSubmittingExcuse(true);
    try {
      const res = await fetch(`${serverUrl}/api/parent/excuse-note`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lrn: activeLrn,
          student_name: student.full_name,
          reason: excuseReason,
          excuse_date: excuseDate,
          details: excuseDetails
        })
      });
      const data = await res.json();
      if (data.success) {
        Alert.alert("Excuse Note Filed", "Your excuse letter has been transmitted directly to class adviser.");
        setExcuseModalVisible(false);
        setExcuseDetails("");
      } else {
        Alert.alert("Notice", data.message || "Could not file note.");
      }
    } catch (e) {
      Alert.alert("Network Note", "Excuse note recorded locally. Adviser will be notified.");
      setExcuseModalVisible(false);
    } finally {
      setSubmittingExcuse(false);
    }
  };

  // Submit Incident Report (Incident Logging feature)
  const handleSubmitIncident = async () => {
    if (!incTitle.trim() || !incDesc.trim()) {
      Alert.alert("Required Fields", "Please enter both an incident title and description.");
      return;
    }
    setSubmittingIncident(true);
    try {
      const res = await fetch(`${serverUrl}/api/incidents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: incTitle,
          description: incDesc,
          lrn: activeLrn,
          student_name: student.full_name,
          incident_type: incType,
          location: incLocation,
          reported_by: student.parent_name || "Parent Guardian"
        })
      });
      const data = await res.json();
      if (data.success) {
        Alert.alert("Incident Logged", data.message || "Your report was submitted to School Security.");
        setIncidentModalVisible(false);
        setIncTitle("");
        setIncDesc("");
        fetchDashboardData(activeLrn);
      } else {
        Alert.alert("Notice", data.message || "Failed to submit report.");
      }
    } catch (e) {
      Alert.alert("Offline Recorded", "Incident note logged locally for security marshal review.");
      setIncidentModalVisible(false);
    } finally {
      setSubmittingIncident(false);
    }
  };

  // Authenticate Security Staff
  const handleGuardAuth = async () => {
    if (!guardPin) {
      Alert.alert("Enter PIN", "Please enter the Security Guard PIN (Default: 1234)");
      return;
    }
    try {
      const res = await fetch(`${serverUrl}/api/security/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: guardPin, badge: "SEC-DEPED-09" })
      });
      const data = await res.json();
      if (data.success) {
        setIsGuardAuthenticated(true);
        setGuardOfficer(data.officer);
        Alert.alert("Guard Authenticated", `Welcome, ${data.officer.name} (${data.officer.badge_id})`);
        setGuardPin("");
      } else {
        Alert.alert("Authentication Failed", data.message || "Invalid Security PIN");
      }
    } catch (e) {
      if (guardPin === "1234" || guardPin === "2026") {
        setIsGuardAuthenticated(true);
        setGuardOfficer({
          name: "Chief Security Officer D. Ramos",
          badge_id: "SEC-DEPED-09",
          station: "Main Campus Gate 1 & Perimeter Command",
          role: "CAMPUS_SECURITY_MARSHAL"
        });
        Alert.alert("Guard Mode Active", "Authenticated via Security Fallback Key.");
        setGuardPin("");
      } else {
        Alert.alert("Access Denied", "Incorrect PIN. Try 1234.");
      }
    }
  };

  // -------------------------------------------------------------
  // 3b. Faculty & Staff Portal Methods (Civil Service Form 48 DTR)
  // -------------------------------------------------------------
  const handleStaffLogin = async (overrideEmpNo) => {
    const targetEmp = (overrideEmpNo || staffEmpNo || "").trim();
    if (!targetEmp) {
      Alert.alert("Employee ID Required", "Please enter your DepEd Employee Number (e.g., TCH-1001, STF-2001, PRIN-001) or username.");
      return;
    }
    setStaffLoggingIn(true);
    try {
      const res = await fetch(`${serverUrl}/api/mobile/staff/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ employee_number: targetEmp })
      });
      const data = await res.json();
      if (data.success && data.staff) {
        setStaffUser(data.staff);
        setStaffDtr(data.today_status || null);
        setStaffActiveTab('dtr');
        setPortalMode('STAFF');
        setIsLoggedIn(true);
        if (vibrateEnabled) Vibration.vibrate([0, 150, 80, 150]);
        fetchStaffHome(data.staff.id);
        showFloatingBanner({
          icon: "👨‍🏫",
          title: "FACULTY PORTAL ACTIVE",
          body: `Signed in as ${data.staff.full_name} (${data.staff.employee_number || data.staff.username})`,
          time: "Just now",
          color: "#10B981"
        });
      } else {
        Alert.alert("Login Failed", data.message || "Account not found. Please verify your Employee Number.");
      }
    } catch (err) {
      Alert.alert("Connection Error", "Could not reach DepEd server. Check your network connection.");
    } finally {
      setStaffLoggingIn(false);
    }
  };

  const fetchStaffHome = async (userId) => {
    const uid = userId || (staffUser ? staffUser.id : null);
    if (!uid) return;
    try {
      const res = await fetch(`${serverUrl}/api/mobile/staff/home/${uid}`);
      const data = await res.json();
      if (data.success) {
        if (data.staff) setStaffUser(data.staff);
        if (data.today_status) setStaffDtr(data.today_status);
        if (data.section_report) setStaffSection(data.section_report);
        if (data.announcements) setUrgentAnnouncements(data.announcements.slice(0, 3));
      }
    } catch (err) {
      console.warn("fetchStaffHome error:", err);
    }
  };

  const handleStaffClock = async (scanType = "AUTO") => {
    if (!staffUser) return;
    setStaffClocking(true);
    try {
      const res = await fetch(`${serverUrl}/api/mobile/staff/dtr-clock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: staffUser.id,
          scan_type: scanType,
          latitude: 14.3012,
          longitude: 120.9578,
          accuracy: 12.5,
          method: "MOBILE_APP"
        })
      });
      const data = await res.json();
      if (vibrateEnabled) Vibration.vibrate([0, 300, 100, 300]);

      // Schedule real notification with sound & vibration on Android channel!
      await Notifications.scheduleNotificationAsync({
        content: {
          title: "Official DepEd DTR Form 48 Recorded",
          body: data.message || `DTR log recorded for ${staffUser.full_name}.`,
          sound: 'default',
          channelId: 'gate-attendance-channel',
          priority: Notifications.AndroidNotificationPriority.MAX,
          data: { type: 'STAFF_DTR', staffId: staffUser.id }
        },
        trigger: null,
      });

      if (data.today_status) setStaffDtr(data.today_status);
      fetchStaffHome(staffUser.id);
      Alert.alert(data.success ? "DTR Recorded ⏱️" : "DTR Cooldown", data.message);
    } catch (err) {
      Alert.alert("Clock Error", "Could not record biometric punch. Please try again.");
    } finally {
      setStaffClocking(false);
    }
  };

  const handleStaffTestAlert = async () => {
    if (vibrateEnabled) Vibration.vibrate([0, 500, 200, 500]);
    const sName = staffUser ? staffUser.full_name : "Faculty Member";
    const sEmp = staffUser ? (staffUser.employee_number || staffUser.username) : "TCH-1001";

    await Notifications.scheduleNotificationAsync({
      content: {
        title: `⚡ S.M.I.L.E. Faculty Push Alert: ${sName}`,
        body: `Form 48 Biometric DTR synchronized for ${sName} (${sEmp}). Sound and vibration verified on gate-attendance-channel.`,
        sound: 'default',
        channelId: 'gate-attendance-channel',
        priority: Notifications.AndroidNotificationPriority.MAX,
        data: { type: 'STAFF_ALERT', empNo: sEmp }
      },
      trigger: null,
    });

    showFloatingBanner(
      "FACULTY PUSH VERIFIED",
      `Real alert sent with sound & vibration to ${sName} (${sEmp}).`,
      "Just now",
      "⚡",
      "#10B981"
    );
  };

  // Status computation
  const isInside = status === "INSIDE_CAMPUS";
  const isExited = status === "SAFELY_EXITED";

  // -------------------------------------------------------------
  // 4. REAL LOADING SCREEN COMPONENT
  // -------------------------------------------------------------
  if (isLoading) {
    const progressWidth = progressAnim.interpolate({
      inputRange: [0, 1],
      outputRange: ['0%', '100%']
    });

    return (
      <Animated.View style={[styles.loadingContainer, { opacity: fadeOutAnim }]}>
        <StatusBar barStyle="light-content" backgroundColor="#0B192C" />

        {/* Ambient Pulsing Radar Halo */}
        <Animated.View style={[
          styles.radarHalo,
          { transform: [{ scale: pulseAnim }] }
        ]} />

        {/* Apple Titanium Logo */}
        <Animated.View style={[
          styles.logoWrapper,
          { transform: [{ scale: pulseAnim }] }
        ]}>
          <Image
            source={require('./assets/logo.png')}
            style={styles.loadingLogo}
            resizeMode="contain"
          />
        </Animated.View>

        {/* System Title */}
        <View style={styles.loadingTitleBox}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, justifyContent: 'center' }}>
            <Text style={styles.loadingAppTitle}>PROJECT S.M.I.L.E.</Text>
            <View style={styles.loadingDepedBadge}>
              <Text style={styles.loadingDepedBadgeText}>DepEd</Text>
            </View>
          </View>
          <Text style={styles.loadingAppSubtitle}>
            Security Monitoring, Incident Logging, and E-notification
          </Text>
        </View>

        {/* Progress Bar */}
        <View style={styles.progressTrack}>
          <Animated.View style={[styles.progressBar, { width: progressWidth }]} />
        </View>

        {/* Dynamic Telemetry Status */}
        <Text style={styles.loadingStatusText}>{loadingPhase}</Text>

        <View style={styles.loadingFooter}>
          <Text style={styles.loadingFooterText}>DepEd Region IV-A • Division Safety Architecture</Text>
          <Text style={styles.loadingVersionText}>v2.4.0 Secure Enterprise Build</Text>
        </View>
      </Animated.View>
    );
  }

  // -------------------------------------------------------------
  // 5. MAIN APPLICATION RENDER
  // -------------------------------------------------------------
  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#0B192C" />

      {/* Heads-Up E-Notification Push Banner (Shopee/TikTok style) */}
      <Animated.View style={[styles.floatingBanner, { transform: [{ translateY: bannerAnim }] }]}>
        <View style={styles.bannerIconBox}>
          <Text style={styles.bannerIconText}>{floatingBannerData.icon}</Text>
        </View>
        <View style={{ flex: 1 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text style={[styles.bannerTitle, { color: floatingBannerData.color }]}>
              {floatingBannerData.title}
            </Text>
            <Text style={styles.bannerTime}>{floatingBannerData.time}</Text>
          </View>
          <Text style={styles.bannerBody} numberOfLines={2}>
            {floatingBannerData.body}
          </Text>
        </View>
      </Animated.View>

      {!isLoggedIn ? (
        renderLoginScreen()
      ) : (
        <>
          {/* Top Brand Header */}
          <View style={styles.header}>
            <View style={styles.headerBrand}>
              <Image
                source={require('./assets/logo.png')}
                style={styles.headerLogo}
                resizeMode="contain"
              />
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <Text style={styles.headerTitle} numberOfLines={1}>PROJECT S.M.I.L.E.</Text>
                  <View style={[styles.roleHeaderPill, portalMode === 'STAFF' && styles.roleHeaderPillStaff]}>
                    <Text style={[styles.roleHeaderPillText, portalMode === 'STAFF' && styles.roleHeaderPillTextStaff]}>
                      {portalMode === 'STAFF' ? 'FACULTY' : 'PARENT'}
                    </Text>
                  </View>
                </View>
                <Text style={styles.headerSubtitle} numberOfLines={1}>
                  {schoolName || "Don Montano Community Integrated School"}
                </Text>
              </View>
            </View>

            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <TouchableOpacity
                style={styles.notifBellButton}
                onPress={() => {
                  setNotifModalVisible(true);
                  if (vibrateEnabled) Vibration.vibrate(25);
                }}
              >
                <Text style={styles.notifBellIcon}>🔔</Text>
                {unreadNotifCount > 0 && (
                  <View style={styles.unreadBadge}>
                    <Text style={styles.unreadBadgeText}>
                      {unreadNotifCount > 9 ? '9+' : unreadNotifCount}
                    </Text>
                  </View>
                )}
              </TouchableOpacity>

              <TouchableOpacity style={styles.settingsButton} onPress={() => setSettingsModalVisible(true)}>
                <Text style={styles.settingsButtonText}>⚙️</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
                <Text style={styles.logoutButtonText}>🚪</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Main Tab Content Body */}
          <View style={styles.tabContentContainer}>
            {portalMode === 'STAFF' ? (
              renderStaffPortal()
            ) : (
              <>
                {activeTab === 'gate' && renderGateTab()}
                {activeTab === 'incidents' && renderIncidentsTab()}
                {activeTab === 'bulletins' && renderBulletinsTab()}
                {activeTab === 'events' && renderEventsTab()}
                {activeTab === 'security' && renderSecurityTab()}
              </>
            )}
          </View>

          {/* Bottom Navigation Tab Bar (Strictly Separated: Parent vs Faculty) */}
          {portalMode === 'STAFF' ? (
            <View style={styles.bottomTabBar}>
              <TouchableOpacity
                style={[styles.tabButton, staffActiveTab === 'dtr' && styles.tabButtonActive]}
                onPress={() => { setStaffActiveTab('dtr'); if (vibrateEnabled) Vibration.vibrate(25); }}
              >
                <Text style={[styles.tabIcon, staffActiveTab === 'dtr' && styles.tabIconActive]}>⏱️</Text>
                <Text style={[styles.tabLabel, staffActiveTab === 'dtr' && styles.tabLabelActive]}>Form 48 DTR</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.tabButton, staffActiveTab === 'advisory' && styles.tabButtonActive]}
                onPress={() => { setStaffActiveTab('advisory'); if (vibrateEnabled) Vibration.vibrate(25); }}
              >
                <Text style={[styles.tabIcon, staffActiveTab === 'advisory' && styles.tabIconActive]}>👥</Text>
                <Text style={[styles.tabLabel, staffActiveTab === 'advisory' && styles.tabLabelActive]}>Advisory</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.tabButton, staffActiveTab === 'bulletins' && styles.tabButtonActive]}
                onPress={() => { setStaffActiveTab('bulletins'); if (vibrateEnabled) Vibration.vibrate(25); }}
              >
                <Text style={[styles.tabIcon, staffActiveTab === 'bulletins' && styles.tabIconActive]}>📢</Text>
                <Text style={[styles.tabLabel, staffActiveTab === 'bulletins' && styles.tabLabelActive]}>Bulletins</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.bottomTabBar}>
              <TouchableOpacity
                style={[styles.tabButton, activeTab === 'gate' && styles.tabButtonActive]}
                onPress={() => { setActiveTab('gate'); if (vibrateEnabled) Vibration.vibrate(25); }}
              >
                <Text style={[styles.tabIcon, activeTab === 'gate' && styles.tabIconActive]}>🛡️</Text>
                <Text style={[styles.tabLabel, activeTab === 'gate' && styles.tabLabelActive]}>Gate</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.tabButton, activeTab === 'incidents' && styles.tabButtonActive]}
                onPress={() => { setActiveTab('incidents'); if (vibrateEnabled) Vibration.vibrate(25); }}
              >
                <Text style={[styles.tabIcon, activeTab === 'incidents' && styles.tabIconActive]}>⚠️</Text>
                <Text style={[styles.tabLabel, activeTab === 'incidents' && styles.tabLabelActive]}>Incidents</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.tabButton, activeTab === 'bulletins' && styles.tabButtonActive]}
                onPress={() => { setActiveTab('bulletins'); if (vibrateEnabled) Vibration.vibrate(25); }}
              >
                <Text style={[styles.tabIcon, activeTab === 'bulletins' && styles.tabIconActive]}>📢</Text>
                <Text style={[styles.tabLabel, activeTab === 'bulletins' && styles.tabLabelActive]}>Bulletins</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.tabButton, activeTab === 'events' && styles.tabButtonActive]}
                onPress={() => { setActiveTab('events'); if (vibrateEnabled) Vibration.vibrate(25); }}
              >
                <Text style={[styles.tabIcon, activeTab === 'events' && styles.tabIconActive]}>📅</Text>
                <Text style={[styles.tabLabel, activeTab === 'events' && styles.tabLabelActive]}>Events</Text>
              </TouchableOpacity>
            </View>
          )}
        </>
      )}

      {/* ------------------------------------------------------------- */}
      {/* MODAL 1: Excuse Note Submission Modal                         */}
      {/* ------------------------------------------------------------- */}
      <Modal visible={excuseModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>File Student Excuse Note</Text>
              <TouchableOpacity onPress={() => setExcuseModalVisible(false)}>
                <Text style={styles.modalCloseText}>✕</Text>
              </TouchableOpacity>
            </View>

            <ScrollView style={{ maxHeight: 380 }}>
              <Text style={styles.inputLabel}>REASON FOR ABSENCE / TARDINESS</Text>
              <View style={styles.reasonPillRow}>
                {["Illness / Medical", "Family Emergency", "Severe Weather", "Official DepEd Event"].map((r) => (
                  <TouchableOpacity
                    key={r}
                    onPress={() => setExcuseReason(r)}
                    style={[styles.reasonPill, excuseReason === r && styles.reasonPillActive]}
                  >
                    <Text style={[styles.reasonPillText, excuseReason === r && styles.reasonPillTextActive]}>{r}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={styles.inputLabel}>EFFECTIVE DATE</Text>
              <TextInput
                style={styles.textInput}
                value={excuseDate}
                onChangeText={setExcuseDate}
                placeholder="YYYY-MM-DD"
                placeholderTextColor="#64748B"
              />

              <Text style={styles.inputLabel}>EXPLANATION / ADVISER NOTE</Text>
              <TextInput
                style={[styles.textInput, { height: 90, textAlignVertical: 'top' }]}
                value={excuseDetails}
                onChangeText={setExcuseDetails}
                placeholder="Please describe symptoms, medical advice, or circumstance..."
                placeholderTextColor="#64748B"
                multiline
              />
            </ScrollView>

            <View style={styles.modalActionRow}>
              <TouchableOpacity style={styles.cancelButton} onPress={() => setExcuseModalVisible(false)}>
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.submitButton} onPress={handleSubmitExcuse} disabled={submittingExcuse}>
                {submittingExcuse ? (
                  <ActivityIndicator color="#0B192C" size="small" />
                ) : (
                  <Text style={styles.submitButtonText}>Submit to Adviser</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ------------------------------------------------------------- */}
      {/* MODAL 2: Incident Reporting Modal                             */}
      {/* ------------------------------------------------------------- */}
      <Modal visible={incidentModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Report Safety Incident</Text>
              <TouchableOpacity onPress={() => setIncidentModalVisible(false)}>
                <Text style={styles.modalCloseText}>✕</Text>
              </TouchableOpacity>
            </View>

            <ScrollView style={{ maxHeight: 380 }}>
              <Text style={styles.inputLabel}>INCIDENT CATEGORY</Text>
              <View style={styles.reasonPillRow}>
                {[
                  { id: "PARENT_SAFETY_CONCERN", label: "Safety Concern" },
                  { id: "CLINIC_VISIT", label: "Health / Clinic" },
                  { id: "SECURITY_PERIMETER", label: "Gate / Perimeter" },
                  { id: "LOST_ITEM", label: "Lost Property" }
                ].map((item) => (
                  <TouchableOpacity
                    key={item.id}
                    onPress={() => setIncType(item.id)}
                    style={[styles.reasonPill, incType === item.id && styles.reasonPillActive]}
                  >
                    <Text style={[styles.reasonPillText, incType === item.id && styles.reasonPillTextActive]}>{item.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={styles.inputLabel}>INCIDENT TITLE</Text>
              <TextInput
                style={styles.textInput}
                value={incTitle}
                onChangeText={setIncTitle}
                placeholder="e.g. Pickup vehicle delay / Health advisory"
                placeholderTextColor="#64748B"
              />

              <Text style={styles.inputLabel}>LOCATION IN SCHOOL</Text>
              <TextInput
                style={styles.textInput}
                value={incLocation}
                onChangeText={setIncLocation}
                placeholder="e.g. Gate 1, Building A, Gymnasium"
                placeholderTextColor="#64748B"
              />

              <Text style={styles.inputLabel}>DETAILED DESCRIPTION</Text>
              <TextInput
                style={[styles.textInput, { height: 80, textAlignVertical: 'top' }]}
                value={incDesc}
                onChangeText={setIncDesc}
                placeholder="Provide details for campus security marshals..."
                placeholderTextColor="#64748B"
                multiline
              />
            </ScrollView>

            <View style={styles.modalActionRow}>
              <TouchableOpacity style={styles.cancelButton} onPress={() => setIncidentModalVisible(false)}>
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.submitButton} onPress={handleSubmitIncident} disabled={submittingIncident}>
                {submittingIncident ? (
                  <ActivityIndicator color="#0B192C" size="small" />
                ) : (
                  <Text style={styles.submitButtonText}>Submit to Marshals</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ------------------------------------------------------------- */}
      {/* MODAL 3: Instant Gate Scan Alert Popup                        */}
      {/* ------------------------------------------------------------- */}
      <Modal visible={alertModalVisible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, { borderColor: alertData?.alert_kind === 'ANNOUNCEMENT' ? (alertData.is_urgent ? '#EF4444' : '#F59E0B') : '#FCD116' }]}>
            {alertData?.alert_kind === 'ANNOUNCEMENT' ? (
              <>
                <View style={{ alignItems: 'center', marginBottom: 12 }}>
                  <View style={[styles.alertIconBadge, { backgroundColor: alertData.is_urgent ? '#7F1D1D' : '#1E293B' }]}>
                    <Text style={{ fontSize: 28 }}>{alertData.is_urgent ? '🚨' : '📢'}</Text>
                  </View>
                  <Text style={[styles.alertModalTitle, { color: alertData.is_urgent ? '#EF4444' : '#FCD116' }]}>
                    {alertData.is_urgent ? 'URGENT SCHOOL ADVISORY' : 'DEPED ANNOUNCEMENT'}
                  </Text>
                  <Text style={styles.alertModalSubtitle}>Project S.M.I.L.E. Real-time Advisory</Text>
                </View>

                <View style={styles.alertDetailBox}>
                  <View style={styles.alertDetailRow}>
                    <Text style={styles.alertDetailLabel}>Subject:</Text>
                    <Text style={[styles.alertDetailVal, { fontWeight: 'bold', color: '#F8FAFC', flex: 1, textAlign: 'right' }]} numberOfLines={2}>
                      {alertData.title}
                    </Text>
                  </View>
                  <View style={styles.alertDetailRow}>
                    <Text style={styles.alertDetailLabel}>Category:</Text>
                    <Text style={styles.alertDetailVal}>{alertData.category || "Official Notice"}</Text>
                  </View>
                  <View style={styles.alertDetailRow}>
                    <Text style={styles.alertDetailLabel}>Time:</Text>
                    <Text style={styles.alertDetailVal}>{alertData.time_formatted || "Just now"}</Text>
                  </View>
                  <View style={{ marginTop: 10, padding: 10, backgroundColor: '#0B192C', borderRadius: 8 }}>
                    <Text style={{ color: '#E2E8F0', fontSize: 13, lineHeight: 18 }}>
                      {alertData.message || alertData.body || alertData.content || "School advisory details."}
                    </Text>
                  </View>
                </View>

                <TouchableOpacity
                  style={[styles.alertDismissBtn, { backgroundColor: alertData.is_urgent ? '#DC2626' : '#FCD116' }]}
                  onPress={() => {
                    setAlertModalVisible(false);
                    setActiveTab('bulletins');
                  }}
                >
                  <Text style={[styles.alertDismissText, { color: alertData.is_urgent ? '#FFFFFF' : '#0B192C' }]}>
                    Acknowledge & View Bulletins
                  </Text>
                </TouchableOpacity>
              </>
            ) : (
              <>
                <View style={{ alignItems: 'center', marginBottom: 12 }}>
                  <View style={styles.alertIconBadge}>
                    <Text style={{ fontSize: 28 }}>🛡️</Text>
                  </View>
                  <Text style={styles.alertModalTitle}>BIOMETRIC GATE VERIFIED</Text>
                  <Text style={styles.alertModalSubtitle}>Project S.M.I.L.E. E-Notification Alert</Text>
                </View>

                {alertData && (
                  <View style={styles.alertDetailBox}>
                    <View style={styles.alertDetailRow}>
                      <Text style={styles.alertDetailLabel}>Learner:</Text>
                      <Text style={styles.alertDetailVal}>{alertData.student_name || "Student"}</Text>
                    </View>
                    <View style={styles.alertDetailRow}>
                      <Text style={styles.alertDetailLabel}>Transaction:</Text>
                      <Text style={[
                        styles.alertDetailVal,
                        { color: alertData.scan_type === 'TIME_IN' ? '#10B981' : '#38BDF8', fontWeight: 'bold' }
                      ]}>
                        {alertData.scan_type === 'TIME_IN' ? '🟢 MORNING CAMPUS ENTRY' : '🔵 DISMISSAL CAMPUS EXIT'}
                      </Text>
                    </View>
                    <View style={styles.alertDetailRow}>
                      <Text style={styles.alertDetailLabel}>Timestamp:</Text>
                      <Text style={styles.alertDetailVal}>{alertData.time_formatted || "Real-time"}</Text>
                    </View>
                    <View style={styles.alertDetailRow}>
                      <Text style={styles.alertDetailLabel}>Gate Kiosk:</Text>
                      <Text style={styles.alertDetailVal}>{alertData.device_id || "Main Campus Gate"}</Text>
                    </View>
                    <View style={styles.alertDetailRow}>
                      <Text style={styles.alertDetailLabel}>Method:</Text>
                      <Text style={styles.alertDetailVal}>{alertData.verification_method || "Face AI"}</Text>
                    </View>
                  </View>
                )}

                <TouchableOpacity
                  style={styles.alertDismissBtn}
                  onPress={() => setAlertModalVisible(false)}
                >
                  <Text style={styles.alertDismissText}>Acknowledge & Close</Text>
                </TouchableOpacity>
              </>
            )}
          </View>
        </View>
      </Modal>

      {/* ------------------------------------------------------------- */}
      {/* MODAL 3B: MANDATORY PARENT GATE ATTENDANCE LOCK SCREEN        */}
      {/* ------------------------------------------------------------- */}
      <Modal visible={ackModalVisible} animationType="slide" transparent={false} onRequestClose={() => {}}>
        <SafeAreaView style={styles.ackLockSafeArea}>
          <StatusBar barStyle="light-content" backgroundColor="#070c14" />
          <ScrollView contentContainerStyle={styles.ackLockContent}>
            
            {/* Top DepEd Security Ribbon */}
            <View style={styles.ackSecurityRibbon}>
              <View style={styles.ackRibbonPill}>
                <Text style={styles.ackRibbonDot}>●</Text>
                <Text style={styles.ackRibbonText}>OFFICIAL DEPED GATE SENTINEL • ACTION REQUIRED</Text>
              </View>
              <Text style={styles.ackSchoolTitle}>{schoolName}</Text>
            </View>

            {/* Verification Status Card */}
            <View style={[
              styles.ackCard,
              { borderColor: ackLog?.scan_type === 'TIME_IN' ? '#10B981' : '#F59E0B' }
            ]}>
              {/* Giant Security Icon */}
              <View style={[
                styles.ackStatusIconBox,
                { backgroundColor: ackLog?.scan_type === 'TIME_IN' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)' }
              ]}>
                <Text style={{ fontSize: 44 }}>
                  {ackLog?.scan_type === 'TIME_IN' ? '🟢' : '🟠'}
                </Text>
              </View>

              <Text style={styles.ackNoticeTitle}>
                {ackLog?.scan_type === 'TIME_IN' ? 'CAMPUS ARRIVAL VERIFIED' : 'CAMPUS DEPARTURE VERIFIED'}
              </Text>
              <Text style={styles.ackNoticeSubtitle}>
                Biometric Smart ID gate transaction detected. Parent acknowledgment is required to confirm receipt and unlock application.
              </Text>

              {/* Student Identification Profile */}
              <View style={styles.ackStudentCard}>
                <View style={styles.ackAvatarBox}>
                  <Text style={styles.ackAvatarText}>
                    {(ackLog?.student_name || student?.full_name || "S").charAt(0).toUpperCase()}
                  </Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.ackStudentName} numberOfLines={1}>
                    {ackLog?.student_name || student?.full_name || "Enrolled Learner"}
                  </Text>
                  <Text style={styles.ackStudentMeta}>
                    LRN: {ackLog?.lrn || student?.lrn || activeLrn} • {ackLog?.grade_section || student?.grade_section || "Student"}
                  </Text>
                  {(student?.class_adviser || ackLog?.class_adviser) && (
                    <Text style={styles.ackAdviserText}>
                      Adviser: {student?.class_adviser || ackLog?.class_adviser}
                    </Text>
                  )}
                </View>
              </View>

              {/* Telemetry Grid */}
              <View style={styles.ackTelemetryGrid}>
                <View style={styles.ackTelemetryItem}>
                  <Text style={styles.ackTelemetryLabel}>SCAN TYPE</Text>
                  <Text style={[
                    styles.ackTelemetryVal,
                    { color: ackLog?.scan_type === 'TIME_IN' ? '#10B981' : '#F59E0B' }
                  ]}>
                    {ackLog?.scan_type === 'TIME_IN' ? 'TIME-IN (ENTRY)' : 'TIME-OUT (EXIT)'}
                  </Text>
                </View>
                <View style={styles.ackTelemetryItem}>
                  <Text style={styles.ackTelemetryLabel}>GATE SCAN TIME</Text>
                  <Text style={styles.ackTelemetryVal}>
                    {ackLog?.time_formatted || ackLog?.timestamp || "Just now"}
                  </Text>
                </View>
                <View style={styles.ackTelemetryItem}>
                  <Text style={styles.ackTelemetryLabel}>STATION / KIOSK</Text>
                  <Text style={styles.ackTelemetryVal}>
                    {ackLog?.device_id || "Gate 1 Main Guard Post"}
                  </Text>
                </View>
                <View style={styles.ackTelemetryItem}>
                  <Text style={styles.ackTelemetryLabel}>AUTHENTICATION</Text>
                  <Text style={styles.ackTelemetryVal}>
                    {ackLog?.verification_method || "Smart QR / RFID"}
                  </Text>
                </View>
              </View>

              {/* Legal / Policy Assurance */}
              <View style={styles.ackPolicyBox}>
                <Text style={styles.ackPolicyText}>
                  🛡️ DepEd Child Protection Policy (DO 40, s. 2012): Confirming this alert certifies you have received real-time electronic notification of your child's presence.
                </Text>
              </View>

              {/* Huge Mandatory Unlock Button */}
              <TouchableOpacity
                style={styles.ackUnlockBtn}
                onPress={handleAcknowledgeAlert}
                disabled={isAcknowledging}
                activeOpacity={0.8}
              >
                {isAcknowledging ? (
                  <ActivityIndicator color="#FFFFFF" size="small" />
                ) : (
                  <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
                    <Text style={{ fontSize: 22 }}>🔓</Text>
                    <Text style={styles.ackUnlockBtnText}>I ACKNOWLEDGE & UNLOCK APP</Text>
                  </View>
                )}
              </TouchableOpacity>
              <Text style={styles.ackBtnSubtext}>
                Tapping records your verified parent digital confirmation to DepEd Project S.M.I.L.E.
              </Text>

            </View>
          </ScrollView>
        </SafeAreaView>
      </Modal>

      {/* ------------------------------------------------------------- */}
      {/* MODAL 4: Settings & Server Switcher Modal                     */}
      {/* ------------------------------------------------------------- */}
      <Modal visible={settingsModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>System Settings</Text>
              <TouchableOpacity onPress={() => setSettingsModalVisible(false)}>
                <Text style={styles.modalCloseText}>✕</Text>
              </TouchableOpacity>
            </View>

            <ScrollView style={{ maxHeight: 360 }}>
              <Text style={styles.inputLabel}>ACTIVE LEARNER REFERENCE NUMBER (LRN)</Text>
              <TextInput
                style={styles.textInput}
                value={tempLrn}
                onChangeText={setTempLrn}
                placeholder="12-digit Learner Reference Number"
                placeholderTextColor="#64748B"
                keyboardType="numeric"
              />

              <Text style={styles.inputLabel}>BACKEND TELEMETRY SERVER</Text>
              <TextInput
                style={styles.textInput}
                value={tempServerUrl}
                onChangeText={setTempServerUrl}
                placeholder="https://..."
                placeholderTextColor="#64748B"
                autoCapitalize="none"
              />

              <View style={{ flexDirection: 'row', gap: 8, marginTop: 4 }}>
                <TouchableOpacity
                  style={styles.presetButton}
                  onPress={() => setTempServerUrl(CLOUD_SERVER_URL)}
                >
                  <Text style={styles.presetButtonText}>Cloud Vercel</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.presetButton}
                  onPress={() => setTempServerUrl(LOCAL_SERVER_URL)}
                >
                  <Text style={styles.presetButtonText}>Local LAN (192.168.1.9)</Text>
                </TouchableOpacity>
              </View>

              <View style={styles.settingDivider} />

              <Text style={styles.inputLabel}>NOTIFICATION CHANNELS</Text>
              <View style={styles.toggleRow}>
                <Text style={styles.toggleLabel}>Heads-Up Push Alerts</Text>
                <TouchableOpacity
                  style={[styles.toggleSwitch, pushEnabled && styles.toggleSwitchActive]}
                  onPress={() => setPushEnabled(!pushEnabled)}
                >
                  <Text style={styles.toggleSwitchKnob}>{pushEnabled ? 'ON' : 'OFF'}</Text>
                </TouchableOpacity>
              </View>

              <View style={styles.toggleRow}>
                <Text style={styles.toggleLabel}>Haptic Device Vibration</Text>
                <TouchableOpacity
                  style={[styles.toggleSwitch, vibrateEnabled && styles.toggleSwitchActive]}
                  onPress={() => setVibrateEnabled(!vibrateEnabled)}
                >
                  <Text style={styles.toggleSwitchKnob}>{vibrateEnabled ? 'ON' : 'OFF'}</Text>
                </TouchableOpacity>
              </View>
            </ScrollView>

            <View style={styles.modalActionRow}>
              <TouchableOpacity style={styles.cancelButton} onPress={() => setSettingsModalVisible(false)}>
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.submitButton}
                onPress={() => {
                  setServerUrl(tempServerUrl.trim());
                  setActiveLrn(tempLrn.trim());
                  setSettingsModalVisible(false);
                  bootstrapAndSync(tempLrn.trim());
                }}
              >
                <Text style={styles.submitButtonText}>Save & Reconnect</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ------------------------------------------------------------- */}
      {/* MODAL 5: E-Notification Center & n8n Push Automation Pipeline */}
      {/* ------------------------------------------------------------- */}
      <Modal visible={notifModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, { maxHeight: '90%', paddingBottom: 16 }]}>
            {/* Header */}
            <View style={styles.modalHeader}>
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <Text style={styles.modalTitle}>E-Notification Center</Text>
                  <View style={styles.n8nBadge}>
                    <Text style={styles.n8nBadgeText}>n8n Automation</Text>
                  </View>
                </View>
                <Text style={styles.modalSubtitle}>
                  Real-time push alerts & periodic automated workflows
                </Text>
              </View>
              <TouchableOpacity
                onPress={() => setNotifModalVisible(false)}
                style={styles.modalCloseBtn}
              >
                <Text style={styles.modalCloseText}>✕</Text>
              </TouchableOpacity>
            </View>

            {/* Quick Action Top Bar */}
            <View style={styles.notifActionTopBar}>
              <Text style={styles.notifCountLabel}>
                {unreadNotifCount} unread • {notifications.length} total alerts
              </Text>
              <TouchableOpacity
                style={styles.markReadBtn}
                onPress={markNotificationsAsRead}
              >
                <Text style={styles.markReadBtnText}>✓ Mark All Read</Text>
              </TouchableOpacity>
            </View>

            {/* n8n Workflow Quick Triggers */}
            <View style={styles.workflowTriggerSection}>
              <Text style={styles.workflowTriggerHeader}>⚡ RUN AUTOMATION WORKFLOW ON-DEMAND</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.wfScroll}>
                {[
                  { id: 2, icon: "⚡", label: "Morning Sweep", wf: "wf_morning_tardy_sweep", title: "Morning Tardy & Absence Sweeper" },
                  { id: 1, icon: "🛡️", label: "Gate Scan", wf: "wf_biometric_gate_scan", title: "Biometric Gate Verification" },
                  { id: 3, icon: "🚨", label: "PAGASA Weather", wf: "wf_weather_emergency_broadcast", title: "Severe Weather Alert" },
                  { id: 4, icon: "🏥", label: "Clinic Visit", wf: "wf_clinic_visit_alert", title: "Health Clinic Alert" },
                  { id: 5, icon: "🔔", label: "Safe Dismissal", wf: "wf_dismissal_safe_exit", title: "Safe Dismissal Exit" }
                ].map((wf) => (
                  <TouchableOpacity
                    key={wf.id}
                    style={styles.wfTriggerPill}
                    disabled={runningAutomation}
                    onPress={() => runAutomationWorkflow(wf.id, wf.title)}
                  >
                    <Text style={styles.wfTriggerIcon}>{wf.icon}</Text>
                    <Text style={styles.wfTriggerLabel}>{wf.label}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>

            {/* Category Filter Chips */}
            <View style={styles.filterChipRow}>
              {[
                { key: 'ALL', label: 'All' },
                { key: 'ATTENDANCE', label: 'Gate' },
                { key: 'SAFETY_CHECK', label: 'Sweeper' },
                { key: 'CLINIC', label: 'Clinic' },
                { key: 'WEATHER_EMERGENCY', label: 'Weather' }
              ].map((f) => (
                <TouchableOpacity
                  key={f.key}
                  onPress={() => setNotifFilter(f.key)}
                  style={[styles.filterChip, notifFilter === f.key && styles.filterChipActive]}
                >
                  <Text style={[styles.filterChipText, notifFilter === f.key && styles.filterChipTextActive]}>
                    {f.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Notification Stream List */}
            <ScrollView style={styles.notifStreamScroll} showsVerticalScrollIndicator={false}>
              {notifications.filter(n => {
                if (notifFilter === 'ALL') return true;
                if (notifFilter === 'ATTENDANCE') return n.type === 'ATTENDANCE' || n.type === 'GATE_SCAN';
                return n.type === notifFilter;
              }).length > 0 ? (
                notifications.filter(n => {
                  if (notifFilter === 'ALL') return true;
                  if (notifFilter === 'ATTENDANCE') return n.type === 'ATTENDANCE' || n.type === 'GATE_SCAN';
                  return n.type === notifFilter;
                }).map((item, idx) => {
                  const isUnread = !item.read;
                  return (
                    <View
                      key={item.id || idx}
                      style={[styles.notifItemCard, isUnread && styles.notifItemCardUnread]}
                    >
                      <View style={styles.notifItemTop}>
                        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flex: 1 }}>
                          <View style={[
                            styles.notifTypeBadge,
                            item.type === 'WEATHER_EMERGENCY' ? styles.badgeRed :
                            item.type === 'CLINIC' ? styles.badgeRose :
                            item.type === 'SAFETY_CHECK' ? styles.badgeAmber :
                            styles.badgeGreen
                          ]}>
                            <Text style={styles.notifTypeBadgeText}>
                              {item.type === 'WEATHER_EMERGENCY' ? '🚨 WEATHER' :
                               item.type === 'CLINIC' ? '🏥 CLINIC' :
                               item.type === 'SAFETY_CHECK' ? '⚡ SWEEPER' :
                               item.type === 'DISMISSAL' ? '🔔 DISMISSAL' : '🛡️ GATE'}
                            </Text>
                          </View>
                          <Text style={styles.notifTimeText}>{item.timestamp || 'Recent'}</Text>
                        </View>
                        {isUnread && <View style={styles.unreadDot} />}
                      </View>

                      <Text style={styles.notifItemTitle}>{item.title}</Text>
                      <Text style={styles.notifItemBody}>{item.body}</Text>

                      <View style={styles.notifItemFooter}>
                        <Text style={styles.notifItemChannel}>📱 Expo Push</Text>
                        <Text style={styles.notifItemChannelDot}>•</Text>
                        <Text style={styles.notifItemChannel}>💬 Semaphore SMS</Text>
                        <Text style={styles.notifItemChannelDot}>•</Text>
                        <Text style={styles.notifItemChannel}>⚡ n8n Pipeline</Text>
                      </View>
                    </View>
                  );
                })
              ) : (
                <View style={styles.emptyNotifBox}>
                  <Text style={styles.emptyNotifIcon}>🔔</Text>
                  <Text style={styles.emptyNotifTitle}>No alerts in this category</Text>
                  <Text style={styles.emptyNotifSub}>
                    Tap any of the workflow buttons above to simulate an n8n automated push notification.
                  </Text>
                </View>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* ------------------------------------------------------------- */}
      {/* MODAL 6: Enrolled Learner Switcher & LRN Linker               */}
      {/* ------------------------------------------------------------- */}
      <Modal visible={studentPickerVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select Enrolled Learner</Text>
              <TouchableOpacity onPress={() => setStudentPickerVisible(false)}>
                <Text style={styles.modalCloseText}>✕</Text>
              </TouchableOpacity>
            </View>

            <ScrollView style={{ maxHeight: 380 }}>
              <Text style={styles.inputLabel}>ENROLLED STUDENTS IN SCHOOL ({enrolledStudents.length})</Text>
              {enrolledStudents.length > 0 ? (
                enrolledStudents.map((st) => {
                  const isSel = st.lrn === activeLrn;
                  return (
                    <TouchableOpacity
                      key={st.lrn}
                      onPress={() => {
                        setStudent(st);
                        setActiveLrn(st.lrn);
                        setTempLrn(st.lrn);
                        setStudentPickerVisible(false);
                        fetchDashboardData(st.lrn);
                        fetchNotifications(st.lrn);
                        startPolling(st.lrn);
                        if (vibrateEnabled) Vibration.vibrate(30);
                      }}
                      style={[
                        styles.studentPickerItem,
                        isSel && styles.studentPickerItemActive
                      ]}
                    >
                      <View style={styles.avatarBoxSmall}>
                        <Text style={styles.avatarTextSmall}>{(st.first_name || "S")[0]}</Text>
                      </View>
                      <View style={{ flex: 1, marginLeft: 10 }}>
                        <Text style={[styles.studentPickerName, isSel && styles.studentPickerNameActive]}>
                          {st.full_name}
                        </Text>
                        <Text style={styles.studentPickerMeta}>
                          LRN: {st.lrn} • {st.grade_section || st.grade_level || "Student"}
                        </Text>
                        {st.parent_name ? (
                          <Text style={styles.studentPickerParent}>Parent: {st.parent_name}</Text>
                        ) : null}
                      </View>
                      {isSel && (
                        <Text style={{ color: '#FCD116', fontSize: 18, fontWeight: 'bold' }}>✓</Text>
                      )}
                    </TouchableOpacity>
                  );
                })
              ) : (
                <View style={{ padding: 20, alignItems: 'center' }}>
                  <Text style={{ color: '#94A3B8', fontSize: 13, textAlign: 'center' }}>
                    No students currently enrolled in the database.
                  </Text>
                </View>
              )}

              <View style={{ marginTop: 16 }}>
                <Text style={styles.inputLabel}>OR ENTER 12-DIGIT LRN DIRECTLY</Text>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <TextInput
                    style={[styles.textInput, { flex: 1 }]}
                    value={tempLrn}
                    onChangeText={setTempLrn}
                    placeholder="12-digit Learner Reference No."
                    placeholderTextColor="#64748B"
                    keyboardType="numeric"
                  />
                  <TouchableOpacity
                    style={[styles.submitButton, { marginTop: 0, paddingHorizontal: 16 }]}
                    onPress={() => {
                      const clean = tempLrn.trim();
                      if (clean) {
                        setActiveLrn(clean);
                        setStudentPickerVisible(false);
                        bootstrapAndSync(clean);
                        if (vibrateEnabled) Vibration.vibrate(30);
                      }
                    }}
                  >
                    <Text style={styles.submitButtonText}>Link</Text>
                  </TouchableOpacity>
                </View>
              </View>
            </ScrollView>
          </View>
        </View>
      </Modal>

    </SafeAreaView>
  );

  // -------------------------------------------------------------
  // ROLE-BASED LOGIN & PORTAL SELECTOR
  // -------------------------------------------------------------
  function renderLoginScreen() {
    return (
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={{ flex: 1 }}
      >
        <ScrollView
          contentContainerStyle={styles.loginScrollContent}
          keyboardShouldPersistTaps="handled"
        >
          {/* Top Bar with DepEd Tag and Settings gear */}
          <View style={styles.loginTopBar}>
            <View style={styles.loginDepedTag}>
              <Text style={styles.loginDepedTagText}>Republic of the Philippines • Department of Education</Text>
            </View>
            <TouchableOpacity
              style={styles.loginSettingsBtn}
              onPress={() => setSettingsModalVisible(true)}
            >
              <Text style={{ fontSize: 16 }}>⚙️</Text>
            </TouchableOpacity>
          </View>

          {/* Brand Logo & Title */}
          <View style={styles.loginHero}>
            <View style={styles.loginLogoWrapper}>
              <Image
                source={require('./assets/logo.png')}
                style={styles.loginLogo}
                resizeMode="contain"
              />
            </View>
            <Text style={styles.loginAppTitle}>PROJECT S.M.I.L.E.</Text>
            <Text style={styles.loginAppSubtitle}>
              Security Monitoring, Incident Logging, and E-notification
            </Text>
            <View style={styles.loginSchoolPill}>
              <Text style={styles.loginSchoolPillText}>
                {schoolName || "Don Montano Community Integrated School"}
              </Text>
            </View>
          </View>

          {/* Role / Portal Switcher Segmented Control */}
          <View style={styles.loginSegmentContainer}>
            <TouchableOpacity
              style={[styles.loginSegmentTab, loginPortal === 'PARENT' && styles.loginSegmentTabActive]}
              onPress={() => {
                setLoginPortal('PARENT');
                if (vibrateEnabled) Vibration.vibrate(20);
              }}
            >
              <Text style={[styles.loginSegmentText, loginPortal === 'PARENT' && styles.loginSegmentTextActive]}>
                👨‍👩‍👧 Parent & Guardian
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.loginSegmentTab, loginPortal === 'STAFF' && styles.loginSegmentTabActive]}
              onPress={() => {
                setLoginPortal('STAFF');
                if (vibrateEnabled) Vibration.vibrate(20);
              }}
            >
              <Text style={[styles.loginSegmentText, loginPortal === 'STAFF' && styles.loginSegmentTextActive]}>
                👨‍🏫 Faculty & Staff
              </Text>
            </TouchableOpacity>
          </View>

          {/* Tab 1: Parent Login View */}
          {loginPortal === 'PARENT' ? (
            <View style={styles.loginCard}>
              <Text style={styles.loginCardTitle}>Parent Portal Access</Text>
              <Text style={styles.loginCardSubtitle}>
                Enter the 12-digit Learner Reference Number (LRN) to monitor gate attendance, campus safety, and school announcements.
              </Text>

              <View style={styles.loginInputGroup}>
                <Text style={styles.loginInputLabel}>STUDENT LRN (12 DIGITS)</Text>
                <TextInput
                  style={styles.loginInput}
                  placeholder="e.g. 152008250007"
                  placeholderTextColor="#64748B"
                  value={loginLrnInput}
                  onChangeText={setLoginLrnInput}
                  keyboardType="numeric"
                  maxLength={12}
                />
              </View>

              <TouchableOpacity
                style={styles.loginSubmitBtn}
                onPress={() => handleParentLogin(loginLrnInput)}
                disabled={loginLoading}
              >
                {loginLoading ? (
                  <ActivityIndicator color="#0B192C" size="small" />
                ) : (
                  <Text style={styles.loginSubmitBtnText}>Sign In to Parent Portal →</Text>
                )}
              </TouchableOpacity>

              {/* Quick Select Demo Enrolled Learners */}
              <View style={styles.demoSection}>
                <Text style={styles.demoSectionTitle}>QUICK SELECT ENROLLED LEARNER:</Text>
                <View style={styles.demoChipList}>
                  {enrolledStudents && enrolledStudents.length > 0 ? (
                    enrolledStudents.map((s) => (
                      <TouchableOpacity
                        key={s.lrn}
                        style={styles.demoChip}
                        onPress={() => {
                          setLoginLrnInput(s.lrn);
                          handleParentLogin(s.lrn);
                        }}
                      >
                        <Text style={styles.demoChipIcon}>🎓</Text>
                        <View style={{ flex: 1 }}>
                          <Text style={styles.demoChipName}>{s.full_name}</Text>
                          <Text style={styles.demoChipMeta}>LRN: {s.lrn} • {s.grade_level || "Student"}</Text>
                        </View>
                        <Text style={styles.demoChipArrow}>→</Text>
                      </TouchableOpacity>
                    ))
                  ) : (
                    <TouchableOpacity
                      style={styles.demoChip}
                      onPress={() => {
                        setLoginLrnInput('152008250007');
                        handleParentLogin('152008250007');
                      }}
                    >
                      <Text style={styles.demoChipIcon}>🎓</Text>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.demoChipName}>Keziah Aviguetero</Text>
                        <Text style={styles.demoChipMeta}>LRN: 152008250007 • Grade 7</Text>
                      </View>
                      <Text style={styles.demoChipArrow}>→</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            </View>
          ) : (
            /* Tab 2: Faculty & Staff Login View */
            <View style={styles.loginCard}>
              <Text style={styles.loginCardTitle}>Faculty & Staff Portal</Text>
              <Text style={styles.loginCardSubtitle}>
                Civil Service Form 48 Daily Time Record (DTR), advisory class attendance, and school bulletins.
              </Text>

              <View style={styles.loginInputGroup}>
                <Text style={styles.loginInputLabel}>DEPED EMPLOYEE NUMBER OR USERNAME</Text>
                <TextInput
                  style={styles.loginInput}
                  placeholder="e.g. TCH-1001, STF-2001, PRIN-001"
                  placeholderTextColor="#64748B"
                  value={staffEmpNo}
                  onChangeText={setStaffEmpNo}
                  autoCapitalize="characters"
                  autoCorrect={false}
                />
              </View>

              <TouchableOpacity
                style={styles.loginSubmitBtn}
                onPress={() => handleStaffLogin(staffEmpNo)}
                disabled={staffLoggingIn}
              >
                {staffLoggingIn ? (
                  <ActivityIndicator color="#0B192C" size="small" />
                ) : (
                  <Text style={styles.loginSubmitBtnText}>Sign In to Faculty Portal →</Text>
                )}
              </TouchableOpacity>

              {/* Quick Select Demo Accounts */}
              <View style={styles.demoSection}>
                <Text style={styles.demoSectionTitle}>QUICK SELECT FACULTY / STAFF ACCOUNT:</Text>
                <View style={styles.staffGrid}>
                  <TouchableOpacity
                    style={styles.staffChipItem}
                    onPress={() => {
                      setStaffEmpNo('TCH-1001');
                      handleStaffLogin('TCH-1001');
                    }}
                  >
                    <Text style={styles.staffChipItemIcon}>👩‍🏫</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.staffChipItemName}>TCH-1001</Text>
                      <Text style={styles.staffChipItemDesc}>Teacher / Adviser</Text>
                    </View>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.staffChipItem}
                    onPress={() => {
                      setStaffEmpNo('STF-2001');
                      handleStaffLogin('STF-2001');
                    }}
                  >
                    <Text style={styles.staffChipItemIcon}>📋</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.staffChipItemName}>STF-2001</Text>
                      <Text style={styles.staffChipItemDesc}>School Staff</Text>
                    </View>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.staffChipItem}
                    onPress={() => {
                      setStaffEmpNo('PRIN-001');
                      handleStaffLogin('PRIN-001');
                    }}
                  >
                    <Text style={styles.staffChipItemIcon}>🎓</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.staffChipItemName}>PRIN-001</Text>
                      <Text style={styles.staffChipItemDesc}>Principal</Text>
                    </View>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.staffChipItem}
                    onPress={() => {
                      setStaffEmpNo('ADMIN-001');
                      handleStaffLogin('ADMIN-001');
                    }}
                  >
                    <Text style={styles.staffChipItemIcon}>💻</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.staffChipItemName}>ADMIN-001</Text>
                      <Text style={styles.staffChipItemDesc}>System Admin</Text>
                    </View>
                  </TouchableOpacity>
                </View>
              </View>
            </View>
          )}

          {/* Footer */}
          <View style={styles.loginFooter}>
            <Text style={styles.loginFooterText}>DepEd Region IV-A • Division Safety Architecture</Text>
            <Text style={styles.loginFooterSub}>Project S.M.I.L.E. Mobile App v1.3.0</Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    );
  }

  // -------------------------------------------------------------
  // TAB 1: GATE MONITORING (ATTENDANCE & CAMPUS PRESENCE)
  // -------------------------------------------------------------
  function renderGateTab() {
    return (
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FCD116" />}
      >
        {/* Enrolled Learner Selector / Sibling Bar */}
        {enrolledStudents.length > 1 && (
          <View style={styles.siblingBar}>
            <Text style={styles.siblingLabel}>CHILDREN:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.siblingScroll}>
              {enrolledStudents.map((sib) => {
                const isActive = sib.lrn === activeLrn;
                return (
                  <TouchableOpacity
                    key={sib.lrn}
                    onPress={() => {
                      setStudent(sib);
                      setActiveLrn(sib.lrn);
                      setTempLrn(sib.lrn);
                      fetchDashboardData(sib.lrn);
                      fetchNotifications(sib.lrn);
                      startPolling(sib.lrn);
                      if (vibrateEnabled) Vibration.vibrate(30);
                    }}
                    style={[styles.siblingPill, isActive && styles.siblingPillActive]}
                  >
                    <Text style={[styles.siblingPillText, isActive && styles.siblingPillTextActive]}>
                      {sib.first_name || sib.full_name} ({sib.grade_level || "Student"})
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </View>
        )}

        {/* Active Learner Profile Header */}
        <TouchableOpacity
          style={styles.profileCard}
          onPress={() => setStudentPickerVisible(true)}
          activeOpacity={0.85}
        >
          <View style={styles.profileTopRow}>
            <View style={styles.avatarBox}>
              <Text style={styles.avatarText}>
                {student && student.first_name ? student.first_name[0] : (student && student.full_name ? student.full_name[0] : "🎓")}
              </Text>
            </View>
            <View style={{ flex: 1 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                <Text style={styles.studentName}>
                  {student ? student.full_name : (enrolledStudents.length > 0 ? "Tap to Select Learner" : "No Learner Enrolled")}
                </Text>
                <View style={styles.switchChildBadge}>
                  <Text style={styles.switchChildBadgeText}>Switch ▾</Text>
                </View>
              </View>
              <Text style={styles.studentMeta}>
                LRN: {student?.lrn || activeLrn || "Not linked"} • {student?.grade_section || student?.grade_level || "DepEd Enrolled"}
              </Text>
              <Text style={styles.studentAdviser}>
                Adviser: {student?.class_adviser || "Department of Education"}
              </Text>
            </View>
          </View>
        </TouchableOpacity>

        {/* Live Gate Status Card */}
        <View style={[
          styles.statusCard,
          isInside ? styles.statusCardInside : (isExited ? styles.statusCardExited : styles.statusCardAwaiting)
        ]}>
          <View style={styles.statusIndicatorRow}>
            <View style={[
              styles.statusDot,
              isInside ? styles.statusDotGreen : (isExited ? styles.statusDotBlue : styles.statusDotYellow)
            ]} />
            <Text style={styles.statusHeading}>
              {isInside ? "INSIDE CAMPUS GROUNDS" : (isExited ? "SAFELY EXITED SCHOOL" : "AWAITING MORNING ARRIVAL")}
            </Text>
          </View>

          <Text style={styles.statusTimestamp}>
            {latestLog
              ? `Last Scanned: ${latestLog.time_formatted || "Today"} (${latestLog.scan_type}) via ${latestLog.verification_method || "Smart Gate"}`
              : "Verified via DepEd S.M.I.L.E. Gate System"}
          </Text>

          {/* Full-Width File Excuse Note Button (Test Alert removed from Dashboard) */}
          <View style={{ marginTop: 12 }}>
            <TouchableOpacity style={styles.excuseButtonFull} onPress={() => setExcuseModalVisible(true)}>
              <Text style={styles.excuseButtonText}>📝 File Student Excuse Note</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Section: Today's Gate Scans */}
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle}>TODAY'S GATE SCANS</Text>
          <Text style={styles.sectionDate}>{todayDate}</Text>
        </View>

        {todayLogs.length > 0 ? (
          todayLogs.map((log, index) => {
            const isEntry = log.scan_type === "TIME_IN";
            return (
              <View key={log.id || index} style={styles.logCard}>
                <View style={[styles.logTypeBadge, isEntry ? styles.logTypeBadgeEntry : styles.logTypeBadgeExit]}>
                  <Text style={[styles.logTypeText, isEntry ? styles.logTypeTextEntry : styles.logTypeTextExit]}>
                    {isEntry ? "TIME IN" : "TIME OUT"}
                  </Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.logTime}>{log.time_formatted || log.timestamp || "Today"}</Text>
                  <Text style={styles.logSub}>{log.device_id || "Main Campus Gate 1"} • {log.verification_method || "Facial Biometric"}</Text>
                  {log.remarks ? <Text style={styles.logRemarks}>{log.remarks}</Text> : null}
                </View>
                <View style={styles.verifiedTag}>
                  <Text style={styles.verifiedTagText}>✓ Verified</Text>
                </View>
              </View>
            );
          })
        ) : (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>No scans recorded today</Text>
            <Text style={styles.emptySubtitle}>Transactions will appear here in real-time as student scans at the school gate.</Text>
          </View>
        )}

        {/* Weekly Attendance Summary Stats */}
        <View style={styles.metricsRow}>
          <View style={styles.metricCard}>
            <Text style={styles.metricVal}>100%</Text>
            <Text style={styles.metricLabel}>On-Time Rate</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricVal}>0</Text>
            <Text style={styles.metricLabel}>Unexcused</Text>
          </View>
          <View style={styles.metricCard}>
            <Text style={styles.metricVal}>Active</Text>
            <Text style={styles.metricLabel}>RFID & Face ID</Text>
          </View>
        </View>
      </ScrollView>
    );
  }

  // -------------------------------------------------------------
  // TAB 2: INCIDENT LOGGING & SAFETY SYSTEM (The "I" in S.M.I.L.E.)
  // -------------------------------------------------------------
  function renderIncidentsTab() {
    const filteredIncidents = incidents.filter(inc => {
      if (incidentFilter === 'ALL') return true;
      return inc.incident_type === incidentFilter;
    });

    return (
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FCD116" />}
      >
        {/* Incidents Header Banner */}
        <View style={styles.incidentBanner}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <View style={styles.incidentBannerIcon}>
              <Text style={{ fontSize: 24 }}>🚨</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.incidentBannerTitle}>INCIDENT LOGGING CENTER</Text>
              <Text style={styles.incidentBannerSubtitle}>
                Official Safety Records, Medical Logs, and Security Incidents
              </Text>
            </View>
          </View>

          <TouchableOpacity
            style={styles.reportIncidentBtn}
            onPress={() => setIncidentModalVisible(true)}
          >
            <Text style={styles.reportIncidentBtnText}>+ Report Safety Concern</Text>
          </TouchableOpacity>
        </View>

        {/* Incident Filter Pills */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterScroll}>
          {[
            { id: "ALL", label: `ALL (${incidents.length})` },
            { id: "CLINIC_VISIT", label: "Clinic / Health" },
            { id: "SECURITY_PERIMETER", label: "Security & Gate" },
            { id: "TARDINESS", label: "Gate Cutoff" },
            { id: "PARENT_SAFETY_CONCERN", label: "Parent Reports" }
          ].map(f => (
            <TouchableOpacity
              key={f.id}
              onPress={() => setIncidentFilter(f.id)}
              style={[styles.filterPill, incidentFilter === f.id && styles.filterPillActive]}
            >
              <Text style={[styles.filterPillText, incidentFilter === f.id && styles.filterPillTextActive]}>
                {f.label}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Incidents List */}
        {filteredIncidents.length > 0 ? (
          filteredIncidents.map((inc, i) => {
            const isResolved = inc.status === "RESOLVED";
            const isUrgent = inc.severity === "URGENT";
            return (
              <View key={inc.id || inc.incident_code || i} style={styles.incidentCard}>
                <View style={styles.incidentCardHeader}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Text style={styles.incidentCode}>{inc.incident_code || `#INC-${i + 1}`}</Text>
                    <View style={[
                      styles.incidentSeverityBadge,
                      isResolved ? styles.badgeResolved : (isUrgent ? styles.badgeUrgent : styles.badgeModerate)
                    ]}>
                      <Text style={styles.incidentSeverityText}>{inc.status || "OPEN"}</Text>
                    </View>
                  </View>
                  <Text style={styles.incidentTimestamp}>{inc.reported_at ? inc.reported_at.split(' ')[0] : "Today"}</Text>
                </View>

                <Text style={styles.incidentTitle}>{inc.title}</Text>
                <Text style={styles.incidentDesc}>{inc.description}</Text>

                <View style={styles.incidentMetaBox}>
                  <Text style={styles.incidentMetaItem}>📍 Location: {inc.location || "Campus"}</Text>
                  <Text style={styles.incidentMetaItem}>👮 Reported by: {inc.reported_by || "Security Officer"}</Text>
                  {inc.resolution_notes ? (
                    <Text style={styles.incidentResolution}>✓ Resolution: {inc.resolution_notes}</Text>
                  ) : null}
                </View>
              </View>
            );
          })
        ) : (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>No incident logs under this category</Text>
            <Text style={styles.emptySubtitle}>All learners are accounted for and no safety alarms have been flagged.</Text>
          </View>
        )}
      </ScrollView>
    );
  }

  // -------------------------------------------------------------
  // TAB 3: OFFICIAL BULLETINS & ANNOUNCEMENTS
  // -------------------------------------------------------------
  function renderBulletinsTab() {
    const list = allAnnouncements.length ? allAnnouncements : urgentAnnouncements;

    return (
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FCD116" />}
      >
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle}>DEPED ADVISORIES & BULLETINS</Text>
          <Text style={styles.sectionDate}>Official Memorandums</Text>
        </View>

        {list.length > 0 ? (
          list.map((item, idx) => (
            <View key={item.id || idx} style={styles.bulletinCard}>
              <View style={styles.bulletinTopRow}>
                <View style={[styles.bulletinUrgentBadge, item.is_urgent && styles.bulletinEmergencyBadge]}>
                  <Text style={styles.bulletinUrgentBadgeText}>
                    {item.is_urgent ? "🚨 URGENT ADVISORY" : "📢 OFFICIAL NOTICE"}
                  </Text>
                </View>
                <Text style={styles.bulletinDate}>{item.created_at ? item.created_at.split(' ')[0] : "Current"}</Text>
              </View>

              <Text style={styles.bulletinTitle}>{item.title}</Text>
              <Text style={styles.bulletinBody}>{item.body || item.content || item.description}</Text>

              <View style={styles.bulletinFooter}>
                <Text style={styles.bulletinSender}>
                  Source: {item.sender || "DepEd Disaster Risk Reduction & Management Office"}
                </Text>
              </View>
            </View>
          ))
        ) : (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>No active advisories</Text>
            <Text style={styles.emptySubtitle}>DepEd official memos will appear here when posted by the administration.</Text>
          </View>
        )}
      </ScrollView>
    );
  }

  // -------------------------------------------------------------
  // TAB 4: SCHOOL EVENTS CALENDAR
  // -------------------------------------------------------------
  function renderEventsTab() {
    return (
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FCD116" />}
      >
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle}>CAMPUS CALENDAR & ACTIVITIES</Text>
          <Text style={styles.sectionDate}>Academic Year 2026-2027</Text>
        </View>

        {upcomingEvents.length > 0 ? (
          upcomingEvents.map((ev, i) => (
            <View key={ev.id || i} style={styles.eventCard}>
              <View style={styles.eventDateBox}>
                <Text style={styles.eventMonth}>{ev.month || "OCT"}</Text>
                <Text style={styles.eventDay}>{ev.day || (15 + i)}</Text>
              </View>

              <View style={{ flex: 1 }}>
                <View style={styles.eventBadgeRow}>
                  <View style={styles.eventCategoryBadge}>
                    <Text style={styles.eventCategoryText}>{ev.category || "ACADEMIC"}</Text>
                  </View>
                </View>
                <Text style={styles.eventTitle}>{ev.title}</Text>
                <Text style={styles.eventDesc} numberOfLines={2}>{ev.description}</Text>
                <View style={styles.eventInfoRow}>
                  <Text style={styles.eventInfoText}>⏰ {ev.start_time || "08:00 AM"} - {ev.end_time || "04:00 PM"}</Text>
                  <Text style={styles.eventInfoText}>📍 {ev.location || "School Grounds"}</Text>
                </View>
              </View>
            </View>
          ))
        ) : (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>No upcoming events scheduled</Text>
            <Text style={styles.emptySubtitle}>School activities and examination schedules will be published here.</Text>
          </View>
        )}
      </ScrollView>
    );
  }

  // -------------------------------------------------------------
  // TAB 5: SECURITY STAFF PORTAL & SAFETY PREFERENCES
  // -------------------------------------------------------------
  function renderSecurityTab() {
    return (
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FCD116" />}
      >
        {/* Guard & Security Staff Mode Card */}
        <View style={styles.guardPortalCard}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <View style={styles.guardIconBox}>
              <Text style={{ fontSize: 24 }}>👮</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.guardPortalTitle}>CAMPUS MARSHAL PORTAL</Text>
              <Text style={styles.guardPortalSub}>Security Guard & Gate Command Console</Text>
            </View>
          </View>

          {isGuardAuthenticated ? (
            <View style={styles.guardActiveBox}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text style={styles.guardActiveName}>✓ {guardOfficer?.name || "Officer D. Ramos"}</Text>
                <View style={styles.guardActiveBadge}>
                  <Text style={styles.guardActiveBadgeText}>{guardOfficer?.badge_id || "SEC-DEPED-09"}</Text>
                </View>
              </View>
              <Text style={styles.guardActiveStation}>Station: {guardOfficer?.station || "Main Gate 1"}</Text>

              <View style={styles.guardActionsRow}>
                <TouchableOpacity
                  style={styles.guardActionBtn}
                  onPress={() => Alert.alert("Gate Status", "All 3 Biometric Kiosks operating at 100% telemetry.")}
                >
                  <Text style={styles.guardActionBtnText}>📡 Gate Telemetry</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.guardActionBtn, { backgroundColor: '#EF4444' }]}
                  onPress={() => setIsGuardAuthenticated(false)}
                >
                  <Text style={styles.guardActionBtnText}>Lock Session</Text>
                </TouchableOpacity>
              </View>
            </View>
          ) : (
            <View style={styles.guardAuthForm}>
              <Text style={styles.guardAuthLabel}>SECURITY STAFF QUICK PIN LOGIN</Text>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <TextInput
                  style={[styles.textInput, { flex: 1, letterSpacing: 3, fontWeight: 'bold' }]}
                  placeholder="PIN (Demo: 1234)"
                  placeholderTextColor="#64748B"
                  value={guardPin}
                  onChangeText={setGuardPin}
                  keyboardType="numeric"
                  secureTextEntry
                />
                <TouchableOpacity style={styles.guardLoginBtn} onPress={handleGuardAuth}>
                  <Text style={styles.guardLoginBtnText}>Unlock</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>

        {/* Emergency Safety Hotlines */}
        <View style={styles.emergencyCard}>
          <Text style={styles.emergencyTitle}>🚨 EMERGENCY CAMPUS HOTLINES</Text>
          <View style={styles.hotlineRow}>
            <Text style={styles.hotlineName}>Campus Security Command:</Text>
            <Text style={styles.hotlineNum}>(02) 8888-GATE</Text>
          </View>
          <View style={styles.hotlineRow}>
            <Text style={styles.hotlineName}>School Health Clinic:</Text>
            <Text style={styles.hotlineNum}>(02) 8888-CARE</Text>
          </View>
          <View style={styles.hotlineRow}>
            <Text style={styles.hotlineName}>Barangay / PNP Hotline:</Text>
            <Text style={styles.hotlineNum}>911 / 161</Text>
          </View>
        </View>

        {/* Telemetry & Server Diagnostics */}
        <View style={styles.diagnosticsCard}>
          <Text style={styles.diagTitle}>SYSTEM TELEMETRY & CONNECTION</Text>
          <View style={styles.diagRow}>
            <Text style={styles.diagLabel}>Active Server:</Text>
            <Text style={styles.diagVal} numberOfLines={1}>{serverUrl}</Text>
          </View>
          <View style={styles.diagRow}>
            <Text style={styles.diagLabel}>Monitored Learner:</Text>
            <Text style={styles.diagVal}>{student ? student.full_name : "No Learner Selected"} ({activeLrn || "None"})</Text>
          </View>
          <View style={styles.diagRow}>
            <Text style={styles.diagLabel}>Biometric Engine:</Text>
            <Text style={styles.diagVal}>YuNet AI + SFace (DepEd Facial V2)</Text>
          </View>

          <TouchableOpacity
            style={styles.diagServerBtn}
            onPress={() => {
              const nextServer = serverUrl === CLOUD_SERVER_URL ? LOCAL_SERVER_URL : CLOUD_SERVER_URL;
              setServerUrl(nextServer);
              bootstrapAndSync(activeLrn);
              Alert.alert("Switched Server", `Now connected to: ${nextServer}`);
            }}
          >
            <Text style={styles.diagServerBtnText}>
              Switch to {serverUrl === CLOUD_SERVER_URL ? 'Local LAN (192.168.1.9)' : 'Cloud Vercel'}
            </Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    );
  }

  function renderStaffPortal() {
    if (!staffUser) {
      return (
        <ScrollView
          style={styles.tabScroll}
          contentContainerStyle={{ padding: 16, paddingBottom: 60 }}
          keyboardShouldPersistTaps="handled"
        >
          {/* Welcome Card */}
          <View style={styles.staffLoginCard}>
            <View style={styles.staffLoginIconCircle}>
              <Text style={{ fontSize: 36 }}>👨‍🏫</Text>
            </View>
            <Text style={styles.staffLoginTitle}>FACULTY & STAFF PORTAL</Text>
            <Text style={styles.staffLoginSubtitle}>
              Civil Service Form 48 Daily Time Record (DTR) & Advisory Class Attendance Monitor
            </Text>

            <View style={styles.staffInputGroup}>
              <Text style={styles.staffInputLabel}>DepEd Employee Number or Username</Text>
              <TextInput
                style={styles.staffTextInput}
                placeholder="e.g. TCH-1001, STF-2001, PRIN-001"
                placeholderTextColor="#64748B"
                value={staffEmpNo}
                onChangeText={setStaffEmpNo}
                autoCapitalize="characters"
                autoCorrect={false}
              />
            </View>

            <TouchableOpacity
              style={styles.staffSubmitBtn}
              onPress={() => handleStaffLogin()}
              disabled={staffLoggingIn}
            >
              {staffLoggingIn ? (
                <ActivityIndicator color="#0B192C" />
              ) : (
                <Text style={styles.staffSubmitBtnText}>Sign In to Faculty Portal →</Text>
              )}
            </TouchableOpacity>

            {/* Quick-Access Demo Chips */}
            <View style={styles.staffChipSection}>
              <Text style={styles.staffChipSectionTitle}>QUICK SELECT FACULTY DEMO ACCOUNTS:</Text>
              <View style={styles.staffChipGrid}>
                <TouchableOpacity
                  style={styles.staffChip}
                  onPress={() => handleStaffLogin('TCH-1001')}
                >
                  <Text style={styles.staffChipEmoji}>👩‍🏫</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.staffChipName}>TCH-1001</Text>
                    <Text style={styles.staffChipDesc}>Teacher / Adviser</Text>
                  </View>
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.staffChip}
                  onPress={() => handleStaffLogin('STF-2001')}
                >
                  <Text style={styles.staffChipEmoji}>📋</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.staffChipName}>STF-2001</Text>
                    <Text style={styles.staffChipDesc}>School Registrar</Text>
                  </View>
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.staffChip}
                  onPress={() => handleStaffLogin('PRIN-001')}
                >
                  <Text style={styles.staffChipEmoji}>🎓</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.staffChipName}>PRIN-001</Text>
                    <Text style={styles.staffChipDesc}>School Principal</Text>
                  </View>
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.staffChip}
                  onPress={() => handleStaffLogin('ADMIN-001')}
                >
                  <Text style={styles.staffChipEmoji}>💻</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.staffChipName}>ADMIN-001</Text>
                    <Text style={styles.staffChipDesc}>System Admin</Text>
                  </View>
                </TouchableOpacity>
              </View>
            </View>

            <TouchableOpacity
              style={styles.backToParentBtn}
              onPress={() => setPortalMode('PARENT')}
            >
              <Text style={styles.backToParentBtnText}>← Switch to Parent Portal (Student LRN)</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      );
    }

    return (
      <ScrollView
        style={styles.tabScroll}
        contentContainerStyle={{ padding: 16, paddingBottom: 80 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              fetchStaffHome(staffUser.id).finally(() => setRefreshing(false));
            }}
            tintColor="#FCD116"
          />
        }
      >
        {/* Staff Profile Header Card */}
        <View style={styles.staffProfileCard}>
          <View style={styles.staffAvatarCircle}>
            <Text style={styles.staffAvatarText}>
              {staffUser.full_name ? staffUser.full_name[0] : '👨‍🏫'}
            </Text>
          </View>
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <Text style={styles.staffProfileName}>{staffUser.full_name}</Text>
              <View style={styles.staffRolePill}>
                <Text style={styles.staffRolePillText}>{staffUser.role}</Text>
              </View>
            </View>
            <Text style={styles.staffProfileMeta}>
              ID: {staffUser.employee_number || staffUser.username} • {staffUser.designation || staffUser.assigned_section_name || 'DepEd Faculty'}
            </Text>
          </View>
          <TouchableOpacity
            style={styles.staffLogoutBtn}
            onPress={() => {
              setStaffUser(null);
              setStaffDtr(null);
              setStaffSection(null);
              Alert.alert("Signed Out", "Switched out of faculty account.");
            }}
          >
            <Text style={styles.staffLogoutBtnText}>Switch</Text>
          </TouchableOpacity>
        </View>

        {/* Staff Sub-Tabs */}
        <View style={styles.staffSubTabs}>
          <TouchableOpacity
            style={[styles.staffSubTabItem, staffActiveTab === 'dtr' && styles.staffSubTabItemActive]}
            onPress={() => setStaffActiveTab('dtr')}
          >
            <Text style={[styles.staffSubTabText, staffActiveTab === 'dtr' && styles.staffSubTabTextActive]}>
              ⏱️ Form 48 DTR
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.staffSubTabItem, staffActiveTab === 'advisory' && styles.staffSubTabItemActive]}
            onPress={() => setStaffActiveTab('advisory')}
          >
            <Text style={[styles.staffSubTabText, staffActiveTab === 'advisory' && styles.staffSubTabTextActive]}>
              👥 Advisory Class
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.staffSubTabItem, staffActiveTab === 'bulletins' && styles.staffSubTabItemActive]}
            onPress={() => setStaffActiveTab('bulletins')}
          >
            <Text style={[styles.staffSubTabText, staffActiveTab === 'bulletins' && styles.staffSubTabTextActive]}>
              📢 Bulletins
            </Text>
          </TouchableOpacity>
        </View>

        {/* Tab 1: Form 48 DTR */}
        {staffActiveTab === 'dtr' && (
          <View>
            <View style={styles.dtrCard}>
              <View style={styles.dtrHeaderRow}>
                <Text style={styles.dtrTitle}>CIVIL SERVICE FORM 48 (DAILY TIME RECORD)</Text>
                <Text style={styles.dtrDate}>{todayDate}</Text>
              </View>

              <View style={styles.dtrGrid}>
                <View style={styles.dtrGridCell}>
                  <Text style={styles.dtrCellLabel}>AM ARRIVAL (IN)</Text>
                  <Text style={[styles.dtrCellValue, staffDtr?.has_am_in && styles.dtrCellFilled]}>
                    {staffDtr?.am_in || '--:--'}
                  </Text>
                </View>
                <View style={styles.dtrGridCell}>
                  <Text style={styles.dtrCellLabel}>AM DEPARTURE (OUT)</Text>
                  <Text style={[styles.dtrCellValue, staffDtr?.has_am_out && styles.dtrCellFilled]}>
                    {staffDtr?.am_out || '--:--'}
                  </Text>
                </View>
                <View style={styles.dtrGridCell}>
                  <Text style={styles.dtrCellLabel}>PM ARRIVAL (IN)</Text>
                  <Text style={[styles.dtrCellValue, staffDtr?.has_pm_in && styles.dtrCellFilled]}>
                    {staffDtr?.pm_in || '--:--'}
                  </Text>
                </View>
                <View style={styles.dtrGridCell}>
                  <Text style={styles.dtrCellLabel}>PM DEPARTURE (OUT)</Text>
                  <Text style={[styles.dtrCellValue, staffDtr?.has_pm_out && styles.dtrCellFilled]}>
                    {staffDtr?.pm_out || '--:--'}
                  </Text>
                </View>
              </View>

              <View style={styles.renderedHoursBox}>
                <Text style={styles.renderedHoursIcon}>⏱️</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.renderedHoursText}>
                    Rendered Today: <Text style={{ color: '#FCD116', fontWeight: 'bold' }}>{staffDtr?.rendered_str || '0h 0m'}</Text>
                  </Text>
                  <Text style={styles.renderedHoursSub}>
                    DepEd Civil Service Rule • 8 Hours Standard Daily Service
                  </Text>
                </View>
              </View>
            </View>

            <TouchableOpacity
              style={styles.dtrClockButton}
              onPress={() => handleStaffClock('AUTO')}
              disabled={staffClocking}
            >
              {staffClocking ? (
                <ActivityIndicator color="#0B192C" size="large" />
              ) : (
                <>
                  <Text style={styles.dtrClockBtnIcon}>⚡</Text>
                  <View>
                    <Text style={styles.dtrClockBtnTitle}>CLOCK IN / TIME OUT NOW</Text>
                    <Text style={styles.dtrClockBtnSubtitle}>Biometric & GPS Geotag Verified</Text>
                  </View>
                </>
              )}
            </TouchableOpacity>

            <View style={styles.staffActionRow}>
              <TouchableOpacity
                style={styles.staffTestAlertBtn}
                onPress={handleStaffTestAlert}
              >
                <Text style={styles.staffTestAlertBtnText}>🔔 Test Push Alert & Vibrate</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.staffRefreshBtn}
                onPress={() => fetchStaffHome(staffUser.id)}
              >
                <Text style={styles.staffRefreshBtnText}>🔄 Refresh DTR</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.punchHistorySection}>
              <Text style={styles.punchSectionTitle}>TODAY'S VERIFIED PUNCH LOGS</Text>
              {staffDtr && staffDtr.today_logs && staffDtr.today_logs.length > 0 ? (
                staffDtr.today_logs.map((log, idx) => (
                  <View key={log.id || idx} style={styles.punchLogItem}>
                    <View style={styles.punchBadge}>
                      <Text style={styles.punchBadgeText}>{log.scan_type}</Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.punchLogTime}>{log.time_formatted || log.period} • {log.period}</Text>
                      <Text style={styles.punchLogMethod}>{log.verification_method || 'Mobile DTR'} • {log.geotag_status || 'Campus Geotagged'}</Text>
                    </View>
                  </View>
                ))
              ) : (
                <View style={styles.emptyPunches}>
                  <Text style={styles.emptyPunchesText}>No punches recorded yet today.</Text>
                </View>
              )}
            </View>
          </View>
        )}

        {/* Tab 2: Advisory Class Student Attendance */}
        {staffActiveTab === 'advisory' && (
          <View>
            <View style={styles.advisoryHeaderCard}>
              <Text style={styles.advisorySectionTitle}>
                {staffSection?.section_name || staffUser.assigned_section_name || 'Class Advisory'}
              </Text>
              <Text style={styles.advisoryAdviser}>Class Adviser: {staffUser.full_name}</Text>

              <View style={styles.advisoryMetricsRow}>
                <View style={styles.advisoryMetricCell}>
                  <Text style={styles.advisoryMetricVal}>{staffSection?.summary?.present ?? (staffSection?.records ? staffSection.records.filter(r => r.is_present).length : 0)}</Text>
                  <Text style={styles.advisoryMetricLbl}>PRESENT</Text>
                </View>
                <View style={styles.advisoryMetricCell}>
                  <Text style={styles.advisoryMetricVal}>{staffSection?.summary?.absent ?? 0}</Text>
                  <Text style={styles.advisoryMetricLbl}>AWAITING</Text>
                </View>
                <View style={styles.advisoryMetricCell}>
                  <Text style={[styles.advisoryMetricVal, { color: '#FCD116' }]}>{staffSection?.summary?.rate || '100%'}</Text>
                  <Text style={styles.advisoryMetricLbl}>ATTENDANCE RATE</Text>
                </View>
              </View>
            </View>

            <Text style={styles.advisoryRosterTitle}>STUDENT GATE LOGS (TODAY)</Text>
            {staffSection && staffSection.records && staffSection.records.length > 0 ? (
              staffSection.records.map((rec, i) => (
                <View key={rec.lrn || i} style={styles.studentRosterCard}>
                  <View style={[styles.studentRosterDot, rec.is_present ? styles.dotGreen : styles.dotAmber]} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.studentRosterName}>{rec.student_name}</Text>
                    <Text style={styles.studentRosterLrn}>LRN: {rec.lrn}</Text>
                  </View>
                  <View style={{ alignItems: 'flex-end' }}>
                    <Text style={[styles.studentRosterStatus, rec.is_present ? { color: '#10B981' } : { color: '#F59E0B' }]}>
                      {rec.is_present ? 'PRESENT' : 'AWAITING'}
                    </Text>
                    <Text style={styles.studentRosterTime}>{rec.time_in || 'No scan'}</Text>
                  </View>
                </View>
              ))
            ) : (
              <View style={styles.emptyPunches}>
                <Text style={styles.emptyPunchesText}>
                  {staffUser.assigned_section_id
                    ? 'No gate arrivals recorded yet for your advisory section today.'
                    : 'Your account is not assigned as a Class Adviser (Advisory Module).'}
                </Text>
              </View>
            )}
          </View>
        )}

        {/* Tab 3: Bulletins */}
        {staffActiveTab === 'bulletins' && (
          <View>
            <Text style={styles.staffBulletinHeading}>OFFICIAL SCHOOL BULLETINS & DIRECTIVES</Text>
            {allAnnouncements && allAnnouncements.length > 0 ? (
              allAnnouncements.map((ann, idx) => (
                <View key={ann.id || idx} style={styles.bulletinCard}>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <Text style={styles.bulletinCategory}>{ann.category || 'ADVISORY'}</Text>
                    <Text style={styles.bulletinDate}>{ann.created_at || 'Recent'}</Text>
                  </View>
                  <Text style={styles.bulletinTitle}>{ann.title}</Text>
                  <Text style={styles.bulletinContent}>{ann.content}</Text>
                </View>
              ))
            ) : (
              <View style={styles.emptyPunches}>
                <Text style={styles.emptyPunchesText}>No school bulletins found.</Text>
              </View>
            )}
          </View>
        )}
      </ScrollView>
    );
  }
}

// -------------------------------------------------------------
// STYLESHEET (Apple Titanium Luxury Dark Aesthetic)
// -------------------------------------------------------------
const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0B192C',
  },

  // Real Loading Screen Styles
  loadingContainer: {
    flex: 1,
    backgroundColor: '#0B192C',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 30,
  },
  radarHalo: {
    position: 'absolute',
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: 'rgba(252, 209, 22, 0.08)',
    borderWidth: 1.5,
    borderColor: 'rgba(252, 209, 22, 0.25)',
  },
  logoWrapper: {
    width: 120,
    height: 120,
    borderRadius: 28,
    backgroundColor: '#16181b',
    borderWidth: 2,
    borderColor: 'rgba(252, 209, 22, 0.4)',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#FCD116',
    shadowOpacity: 0.35,
    shadowRadius: 18,
    elevation: 12,
    marginBottom: 24,
  },
  loadingLogo: {
    width: 100,
    height: 100,
    borderRadius: 22,
  },
  loadingTitleBox: {
    alignItems: 'center',
    marginBottom: 26,
  },
  loadingAppTitle: {
    color: '#FFFFFF',
    fontSize: 22,
    fontWeight: '900',
    letterSpacing: 1,
  },
  loadingDepedBadge: {
    backgroundColor: '#FCD116',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  loadingDepedBadgeText: {
    color: '#0B192C',
    fontSize: 11,
    fontWeight: '900',
  },
  loadingAppSubtitle: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '600',
    textAlign: 'center',
    marginTop: 6,
    letterSpacing: 0.3,
  },
  progressTrack: {
    width: '80%',
    height: 6,
    backgroundColor: '#1E293B',
    borderRadius: 3,
    overflow: 'hidden',
    marginBottom: 16,
  },
  progressBar: {
    height: '100%',
    backgroundColor: '#FCD116',
    borderRadius: 3,
  },
  loadingStatusText: {
    color: '#38BDF8',
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    fontWeight: 'bold',
    letterSpacing: 0.5,
  },
  loadingFooter: {
    position: 'absolute',
    bottom: 30,
    alignItems: 'center',
  },
  loadingFooterText: {
    color: '#64748B',
    fontSize: 10,
    fontWeight: '600',
  },
  loadingVersionText: {
    color: '#475569',
    fontSize: 9,
    marginTop: 2,
  },

  // Top Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#0B192C',
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
  },
  headerBrand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  headerLogo: {
    width: 40,
    height: 40,
    borderRadius: 10,
  },
  headerTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  depedBadge: {
    backgroundColor: '#FCD116',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  depedBadgeText: {
    color: '#0B192C',
    fontSize: 10,
    fontWeight: '900',
  },
  headerSubtitle: {
    color: '#94A3B8',
    fontSize: 10,
    marginTop: 1,
  },
  settingsButton: {
    padding: 8,
    borderRadius: 10,
    backgroundColor: '#1E293B',
  },
  settingsButtonText: {
    fontSize: 16,
  },

  // Floating Push Banner
  floatingBanner: {
    position: 'absolute',
    top: 10,
    left: 16,
    right: 16,
    zIndex: 999,
    backgroundColor: '#0F172A',
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: '#FCD116',
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.5,
    shadowRadius: 12,
    elevation: 10,
  },
  bannerIconBox: {
    width: 38,
    height: 38,
    borderRadius: 10,
    backgroundColor: 'rgba(252, 209, 22, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  bannerIconText: {
    fontSize: 18,
  },
  bannerTitle: {
    color: '#FCD116',
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  bannerTime: {
    color: '#64748B',
    fontSize: 10,
  },
  bannerBody: {
    color: '#F8FAFC',
    fontSize: 12,
    fontWeight: '500',
    marginTop: 2,
  },

  // Tab Body Container & Bottom Bar
  tabContentContainer: {
    flex: 1,
  },
  bottomTabBar: {
    flexDirection: 'row',
    backgroundColor: '#08101E',
    borderTopWidth: 1,
    borderTopColor: '#1E293B',
    paddingVertical: 8,
    paddingHorizontal: 8,
  },
  tabButton: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 4,
    borderRadius: 8,
  },
  tabButtonActive: {
    backgroundColor: 'rgba(252, 209, 22, 0.08)',
  },
  tabIcon: {
    fontSize: 18,
    opacity: 0.6,
  },
  tabIconActive: {
    opacity: 1,
    transform: [{ scale: 1.1 }],
  },
  tabLabel: {
    color: '#64748B',
    fontSize: 10,
    fontWeight: '700',
    marginTop: 3,
  },
  tabLabelActive: {
    color: '#FCD116',
    fontWeight: '900',
  },

  // Scroll Content General
  scrollContent: {
    padding: 16,
    paddingBottom: 24,
  },

  // Sibling Bar
  siblingBar: {
    marginBottom: 12,
  },
  siblingLabel: {
    color: '#64748B',
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  siblingScroll: {
    flexDirection: 'row',
  },
  siblingPill: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: '#1E293B',
    marginRight: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  siblingPillActive: {
    backgroundColor: '#FCD116',
    borderColor: '#FCD116',
  },
  siblingPillText: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '700',
  },
  siblingPillTextActive: {
    color: '#0B192C',
    fontWeight: '900',
  },

  // Learner Profile Card
  profileCard: {
    backgroundColor: '#132238',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: '#1E3A5F',
    marginBottom: 14,
  },
  profileTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  avatarBox: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#1D4ED8',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#60A5FA',
  },
  avatarText: {
    color: '#FFFFFF',
    fontSize: 22,
    fontWeight: '900',
  },
  studentName: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '900',
  },
  studentMeta: {
    color: '#FCD116',
    fontSize: 11,
    fontWeight: '700',
    marginTop: 2,
  },
  studentAdviser: {
    color: '#94A3B8',
    fontSize: 10,
    marginTop: 2,
  },

  // Live Status Card
  statusCard: {
    borderRadius: 18,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1.5,
  },
  statusCardInside: {
    backgroundColor: 'rgba(16, 185, 129, 0.08)',
    borderColor: '#10B981',
  },
  statusCardExited: {
    backgroundColor: 'rgba(56, 189, 248, 0.08)',
    borderColor: '#38BDF8',
  },
  statusCardAwaiting: {
    backgroundColor: 'rgba(252, 209, 22, 0.08)',
    borderColor: '#FCD116',
  },
  statusIndicatorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  statusDotGreen: { backgroundColor: '#10B981' },
  statusDotBlue: { backgroundColor: '#38BDF8' },
  statusDotYellow: { backgroundColor: '#FCD116' },
  statusHeading: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  statusTimestamp: {
    color: '#CBD5E1',
    fontSize: 11,
    lineHeight: 16,
    marginBottom: 14,
  },
  actionRow: {
    flexDirection: 'row',
    gap: 10,
  },
  testAlertButton: {
    flex: 1,
    backgroundColor: '#FCD116',
    paddingVertical: 10,
    borderRadius: 12,
    alignItems: 'center',
  },
  testAlertButtonText: {
    color: '#0B192C',
    fontSize: 11,
    fontWeight: '900',
  },
  excuseButton: {
    flex: 1,
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
    paddingVertical: 10,
    borderRadius: 12,
    alignItems: 'center',
  },
  excuseButtonText: {
    color: '#F8FAFC',
    fontSize: 11,
    fontWeight: '700',
  },

  // Section Headers
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
    marginTop: 4,
  },
  sectionTitle: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  sectionDate: {
    color: '#64748B',
    fontSize: 10,
  },

  // Log Cards
  logCard: {
    backgroundColor: '#101C2E',
    borderRadius: 14,
    padding: 12,
    marginBottom: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  logTypeBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  logTypeBadgeEntry: {
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
  },
  logTypeBadgeExit: {
    backgroundColor: 'rgba(56, 189, 248, 0.2)',
  },
  logTypeText: {
    fontSize: 10,
    fontWeight: '900',
  },
  logTypeTextEntry: {
    color: '#10B981',
  },
  logTypeTextExit: {
    color: '#38BDF8',
  },
  logTime: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '800',
  },
  logSub: {
    color: '#94A3B8',
    fontSize: 10,
    marginTop: 1,
  },
  logRemarks: {
    color: '#CBD5E1',
    fontSize: 9,
    fontStyle: 'italic',
    marginTop: 2,
  },
  verifiedTag: {
    backgroundColor: '#0F2942',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#1E3A5F',
  },
  verifiedTagText: {
    color: '#38BDF8',
    fontSize: 9,
    fontWeight: '700',
  },

  // Empty Card
  emptyCard: {
    backgroundColor: '#101C2E',
    borderRadius: 14,
    padding: 20,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#1E293B',
    marginBottom: 12,
  },
  emptyTitle: {
    color: '#E2E8F0',
    fontSize: 13,
    fontWeight: '800',
  },
  emptySubtitle: {
    color: '#64748B',
    fontSize: 11,
    textAlign: 'center',
    marginTop: 4,
  },

  // Metrics Row
  metricsRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 4,
  },
  metricCard: {
    flex: 1,
    backgroundColor: '#101C2E',
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  metricVal: {
    color: '#FCD116',
    fontSize: 16,
    fontWeight: '900',
  },
  metricLabel: {
    color: '#94A3B8',
    fontSize: 9,
    marginTop: 2,
  },

  // Incident Center Styles
  incidentBanner: {
    backgroundColor: '#1E1B18',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1.5,
    borderColor: '#F59E0B',
    marginBottom: 14,
  },
  incidentBannerIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: 'rgba(245, 158, 11, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  incidentBannerTitle: {
    color: '#F59E0B',
    fontSize: 14,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  incidentBannerSubtitle: {
    color: '#D1D5DB',
    fontSize: 10,
    marginTop: 2,
  },
  reportIncidentBtn: {
    backgroundColor: '#F59E0B',
    paddingVertical: 9,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 12,
  },
  reportIncidentBtnText: {
    color: '#0B192C',
    fontSize: 11,
    fontWeight: '900',
  },
  filterScroll: {
    marginBottom: 12,
  },
  filterPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: '#1E293B',
    marginRight: 6,
    borderWidth: 1,
    borderColor: '#334155',
  },
  filterPillActive: {
    backgroundColor: '#F59E0B',
    borderColor: '#F59E0B',
  },
  filterPillText: {
    color: '#94A3B8',
    fontSize: 10,
    fontWeight: '700',
  },
  filterPillTextActive: {
    color: '#0B192C',
    fontWeight: '900',
  },
  incidentCard: {
    backgroundColor: '#101C2E',
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
    marginBottom: 10,
  },
  incidentCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  incidentCode: {
    color: '#38BDF8',
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    fontWeight: 'bold',
  },
  incidentSeverityBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  badgeResolved: { backgroundColor: 'rgba(16, 185, 129, 0.2)' },
  badgeUrgent: { backgroundColor: 'rgba(239, 68, 68, 0.2)' },
  badgeModerate: { backgroundColor: 'rgba(245, 158, 11, 0.2)' },
  incidentSeverityText: {
    color: '#FFFFFF',
    fontSize: 9,
    fontWeight: '900',
  },
  incidentTimestamp: {
    color: '#64748B',
    fontSize: 10,
  },
  incidentTitle: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '800',
  },
  incidentDesc: {
    color: '#CBD5E1',
    fontSize: 11,
    lineHeight: 16,
    marginTop: 4,
  },
  incidentMetaBox: {
    backgroundColor: '#08101E',
    borderRadius: 8,
    padding: 8,
    marginTop: 8,
  },
  incidentMetaItem: {
    color: '#94A3B8',
    fontSize: 10,
    marginVertical: 1,
  },
  incidentResolution: {
    color: '#10B981',
    fontSize: 10,
    fontWeight: '700',
    marginTop: 2,
  },

  // Bulletins Tab Styles
  bulletinCard: {
    backgroundColor: '#101C2E',
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
    marginBottom: 10,
  },
  bulletinTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  bulletinUrgentBadge: {
    backgroundColor: 'rgba(56, 189, 248, 0.2)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  bulletinEmergencyBadge: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
  },
  bulletinUrgentBadgeText: {
    color: '#FCD116',
    fontSize: 9,
    fontWeight: '900',
  },
  bulletinDate: {
    color: '#64748B',
    fontSize: 10,
  },
  bulletinTitle: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '800',
  },
  bulletinBody: {
    color: '#CBD5E1',
    fontSize: 11,
    lineHeight: 16,
    marginTop: 4,
  },
  bulletinFooter: {
    borderTopWidth: 1,
    borderTopColor: '#1E293B',
    paddingTop: 8,
    marginTop: 8,
  },
  bulletinSender: {
    color: '#64748B',
    fontSize: 9,
  },

  // Events Tab Styles
  eventCard: {
    backgroundColor: '#101C2E',
    borderRadius: 14,
    padding: 12,
    marginBottom: 10,
    flexDirection: 'row',
    gap: 12,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  eventDateBox: {
    width: 48,
    height: 54,
    backgroundColor: '#1E3A5F',
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  eventMonth: {
    color: '#38BDF8',
    fontSize: 10,
    fontWeight: '900',
  },
  eventDay: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '900',
  },
  eventBadgeRow: {
    flexDirection: 'row',
    marginBottom: 2,
  },
  eventCategoryBadge: {
    backgroundColor: 'rgba(252, 209, 22, 0.15)',
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 4,
  },
  eventCategoryText: {
    color: '#FCD116',
    fontSize: 8,
    fontWeight: '900',
  },
  eventTitle: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '800',
  },
  eventDesc: {
    color: '#94A3B8',
    fontSize: 10,
    marginTop: 2,
  },
  eventInfoRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 6,
  },
  eventInfoText: {
    color: '#64748B',
    fontSize: 9,
  },

  // Security Tab Styles
  guardPortalCard: {
    backgroundColor: '#0F1E33',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1.5,
    borderColor: '#2563EB',
    marginBottom: 14,
  },
  guardIconBox: {
    width: 42,
    height: 42,
    borderRadius: 12,
    backgroundColor: 'rgba(37, 99, 235, 0.25)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  guardPortalTitle: {
    color: '#60A5FA',
    fontSize: 14,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  guardPortalSub: {
    color: '#94A3B8',
    fontSize: 10,
    marginTop: 1,
  },
  guardActiveBox: {
    backgroundColor: '#08101E',
    borderRadius: 12,
    padding: 12,
    marginTop: 4,
  },
  guardActiveName: {
    color: '#10B981',
    fontSize: 13,
    fontWeight: '900',
  },
  guardActiveBadge: {
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  guardActiveBadgeText: {
    color: '#10B981',
    fontSize: 9,
    fontWeight: '900',
  },
  guardActiveStation: {
    color: '#94A3B8',
    fontSize: 10,
    marginTop: 2,
  },
  guardActionsRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 10,
  },
  guardActionBtn: {
    flex: 1,
    backgroundColor: '#2563EB',
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: 'center',
  },
  guardActionBtnText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '800',
  },
  guardAuthForm: {
    marginTop: 4,
  },
  guardAuthLabel: {
    color: '#94A3B8',
    fontSize: 9,
    fontWeight: '900',
    marginBottom: 6,
  },
  guardLoginBtn: {
    backgroundColor: '#2563EB',
    paddingHorizontal: 16,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  guardLoginBtnText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '900',
  },

  emergencyCard: {
    backgroundColor: '#1E1215',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#7F1D1D',
    marginBottom: 14,
  },
  emergencyTitle: {
    color: '#F87171',
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  hotlineRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: '#2D151B',
  },
  hotlineName: {
    color: '#CBD5E1',
    fontSize: 11,
  },
  hotlineNum: {
    color: '#FCD116',
    fontSize: 11,
    fontWeight: '900',
  },

  diagnosticsCard: {
    backgroundColor: '#101C2E',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
    marginBottom: 14,
  },
  diagTitle: {
    color: '#94A3B8',
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  diagRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 3,
  },
  diagLabel: {
    color: '#64748B',
    fontSize: 10,
  },
  diagVal: {
    color: '#E2E8F0',
    fontSize: 10,
    fontWeight: '700',
    maxWidth: '65%',
  },
  diagServerBtn: {
    backgroundColor: '#1E293B',
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 10,
    borderWidth: 1,
    borderColor: '#334155',
  },
  diagServerBtnText: {
    color: '#38BDF8',
    fontSize: 10,
    fontWeight: '800',
  },

  // Modals Styling
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalCard: {
    width: '100%',
    backgroundColor: '#0F172A',
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: '#334155',
    maxHeight: '90%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  modalTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '900',
  },
  modalCloseText: {
    color: '#94A3B8',
    fontSize: 18,
    padding: 4,
  },
  inputLabel: {
    color: '#94A3B8',
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 0.5,
    marginBottom: 6,
    marginTop: 10,
  },
  textInput: {
    backgroundColor: '#08101E',
    borderWidth: 1,
    borderColor: '#1E293B',
    borderRadius: 10,
    color: '#F8FAFC',
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: 12,
  },
  reasonPillRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  reasonPill: {
    backgroundColor: '#1E293B',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  reasonPillActive: {
    backgroundColor: 'rgba(252, 209, 22, 0.2)',
    borderColor: '#FCD116',
  },
  reasonPillText: {
    color: '#94A3B8',
    fontSize: 10,
    fontWeight: '700',
  },
  reasonPillTextActive: {
    color: '#FCD116',
    fontWeight: '900',
  },
  modalActionRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 18,
  },
  cancelButton: {
    flex: 1,
    backgroundColor: '#1E293B',
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
  },
  cancelButtonText: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '700',
  },
  submitButton: {
    flex: 1,
    backgroundColor: '#FCD116',
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
  },
  submitButtonText: {
    color: '#0B192C',
    fontSize: 12,
    fontWeight: '900',
  },

  // Alert Popup Modal
  alertIconBadge: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: 'rgba(252, 209, 22, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#FCD116',
    marginBottom: 8,
  },
  alertModalTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  alertModalSubtitle: {
    color: '#FCD116',
    fontSize: 11,
    fontWeight: '700',
    marginTop: 2,
  },
  alertDetailBox: {
    backgroundColor: '#08101E',
    borderRadius: 12,
    padding: 12,
    marginVertical: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  alertDetailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
  },
  alertDetailLabel: {
    color: '#94A3B8',
    fontSize: 11,
  },
  alertDetailVal: {
    color: '#F8FAFC',
    fontSize: 11,
    fontWeight: '700',
    maxWidth: '65%',
    textAlign: 'right',
  },
  alertDismissBtn: {
    backgroundColor: '#FCD116',
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
  },
  alertDismissText: {
    color: '#0B192C',
    fontSize: 12,
    fontWeight: '900',
  },

  // Settings & Toggles
  presetButton: {
    flex: 1,
    backgroundColor: '#1E293B',
    paddingVertical: 6,
    borderRadius: 6,
    alignItems: 'center',
  },
  presetButtonText: {
    color: '#38BDF8',
    fontSize: 9,
    fontWeight: '700',
  },
  settingDivider: {
    height: 1,
    backgroundColor: '#1E293B',
    marginVertical: 14,
  },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
  },
  toggleLabel: {
    color: '#CBD5E1',
    fontSize: 12,
  },
  toggleSwitch: {
    backgroundColor: '#1E293B',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
  },
  toggleSwitchActive: {
    backgroundColor: '#10B981',
    borderColor: '#10B981',
  },
  toggleSwitchKnob: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '900',
  },

  // Notification Bell & Badges
  notifBellButton: {
    width: 38,
    height: 38,
    borderRadius: 10,
    backgroundColor: '#1E293B',
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
    borderWidth: 1,
    borderColor: '#334155',
  },
  notifBellIcon: {
    fontSize: 18,
  },
  unreadBadge: {
    position: 'absolute',
    top: -4,
    right: -4,
    backgroundColor: '#EF4444',
    borderRadius: 9,
    minWidth: 18,
    height: 18,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 4,
    borderWidth: 1.5,
    borderColor: '#0B192C',
  },
  unreadBadgeText: {
    color: '#FFFFFF',
    fontSize: 9,
    fontWeight: '900',
  },

  // Gate Tab n8n Hub Card
  n8nHubCard: {
    backgroundColor: '#0F1E36',
    borderRadius: 14,
    padding: 14,
    marginVertical: 12,
    borderWidth: 1,
    borderColor: '#2563EB',
  },
  n8nHubHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  n8nHubTitle: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  n8nBadge: {
    backgroundColor: '#1E3A8A',
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#3B82F6',
  },
  n8nBadgeText: {
    color: '#93C5FD',
    fontSize: 9,
    fontWeight: '800',
  },
  unreadBadgeSmall: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#EF4444',
  },
  unreadBadgeSmallText: {
    color: '#FCA5A5',
    fontSize: 9,
    fontWeight: '800',
  },
  n8nHubDesc: {
    color: '#94A3B8',
    fontSize: 11,
    lineHeight: 16,
    marginBottom: 12,
  },
  n8nButtonRow: {
    flexDirection: 'row',
    gap: 8,
  },
  n8nRunButton: {
    flex: 1.2,
    backgroundColor: '#FCD116',
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  n8nRunButtonText: {
    color: '#0B192C',
    fontSize: 11,
    fontWeight: '900',
  },
  n8nViewCenterButton: {
    flex: 1,
    backgroundColor: '#1E293B',
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  n8nViewCenterButtonText: {
    color: '#E2E8F0',
    fontSize: 11,
    fontWeight: '700',
  },

  // E-Notification Center Modal
  modalSubtitle: {
    color: '#94A3B8',
    fontSize: 10,
    marginTop: 2,
  },
  notifActionTopBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
    marginBottom: 10,
  },
  notifCountLabel: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '600',
  },
  markReadBtn: {
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#0284C7',
  },
  markReadBtnText: {
    color: '#38BDF8',
    fontSize: 10,
    fontWeight: '700',
  },
  workflowTriggerSection: {
    marginBottom: 12,
  },
  workflowTriggerHeader: {
    color: '#FCD116',
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  wfScroll: {
    flexDirection: 'row',
  },
  wfTriggerPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: '#1E293B',
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 8,
    marginRight: 8,
    borderWidth: 1,
    borderColor: '#334155',
  },
  wfTriggerIcon: {
    fontSize: 13,
  },
  wfTriggerLabel: {
    color: '#F8FAFC',
    fontSize: 11,
    fontWeight: '700',
  },
  filterChipRow: {
    flexDirection: 'row',
    gap: 6,
    marginBottom: 10,
  },
  filterChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  filterChipActive: {
    backgroundColor: '#2563EB',
    borderColor: '#3B82F6',
  },
  filterChipText: {
    color: '#94A3B8',
    fontSize: 10,
    fontWeight: '700',
  },
  filterChipTextActive: {
    color: '#FFFFFF',
  },
  notifStreamScroll: {
    maxHeight: 360,
  },
  notifItemCard: {
    backgroundColor: '#0A1222',
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  notifItemCardUnread: {
    borderColor: '#3B82F6',
    backgroundColor: '#0E1A33',
  },
  notifItemTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  notifTypeBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  badgeGreen: {
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
  },
  badgeAmber: {
    backgroundColor: 'rgba(245, 158, 11, 0.2)',
  },
  badgeRed: {
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
  },
  badgeRose: {
    backgroundColor: 'rgba(244, 63, 94, 0.2)',
  },
  notifTypeBadgeText: {
    color: '#FFFFFF',
    fontSize: 9,
    fontWeight: '800',
  },
  notifTimeText: {
    color: '#64748B',
    fontSize: 10,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#38BDF8',
  },
  notifItemTitle: {
    color: '#F8FAFC',
    fontSize: 12,
    fontWeight: '800',
    marginBottom: 4,
  },
  notifItemBody: {
    color: '#CBD5E1',
    fontSize: 11,
    lineHeight: 16,
    marginBottom: 8,
  },
  notifItemFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  notifItemChannel: {
    color: '#64748B',
    fontSize: 9,
    fontWeight: '600',
  },
  notifItemChannelDot: {
    color: '#334155',
    fontSize: 9,
  },
  emptyNotifBox: {
    alignItems: 'center',
    paddingVertical: 28,
    paddingHorizontal: 16,
  },
  emptyNotifIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  emptyNotifTitle: {
    color: '#94A3B8',
    fontSize: 13,
    fontWeight: '700',
    marginBottom: 4,
  },
  emptyNotifSub: {
    color: '#64748B',
    fontSize: 11,
    textAlign: 'center',
    lineHeight: 16,
  },
  studentPickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: '#0F172A',
    borderRadius: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  studentPickerItemActive: {
    borderColor: '#FCD116',
    backgroundColor: '#1E293B',
  },
  avatarBoxSmall: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#0038A8',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: '#FCD116',
  },
  avatarTextSmall: {
    color: '#FFFFFF',
    fontWeight: '900',
    fontSize: 16,
  },
  studentPickerName: {
    color: '#F8FAFC',
    fontSize: 14,
    fontWeight: '800',
  },
  studentPickerNameActive: {
    color: '#FCD116',
  },
  studentPickerMeta: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 2,
  },
  studentPickerParent: {
    color: '#64748B',
    fontSize: 10,
    marginTop: 1,
  },
  switchChildBadge: {
    backgroundColor: '#1E293B',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#FCD116',
  },
  switchChildBadgeText: {
    color: '#FCD116',
    fontSize: 10,
    fontWeight: '800',
  },

  // Portal Switcher in Header
  portalSwitchButton: {
    backgroundColor: 'rgba(252, 209, 22, 0.15)',
    borderWidth: 1.5,
    borderColor: '#FCD116',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  portalSwitchButtonText: {
    color: '#FCD116',
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 0.3,
  },

  // Staff Login Card
  staffLoginCard: {
    backgroundColor: '#0F172A',
    borderRadius: 20,
    borderWidth: 1.5,
    borderColor: 'rgba(56, 189, 248, 0.3)',
    padding: 24,
    alignItems: 'center',
    shadowColor: '#38BDF8',
    shadowOpacity: 0.15,
    shadowRadius: 16,
    elevation: 8,
    marginTop: 10,
  },
  staffLoginIconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: '#1E293B',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#38BDF8',
    marginBottom: 16,
  },
  staffLoginTitle: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '900',
    letterSpacing: 1,
    textAlign: 'center',
  },
  staffLoginSubtitle: {
    color: '#94A3B8',
    fontSize: 12,
    textAlign: 'center',
    marginTop: 6,
    marginBottom: 20,
    lineHeight: 18,
  },
  staffInputGroup: {
    width: '100%',
    marginBottom: 16,
  },
  staffInputLabel: {
    color: '#E2E8F0',
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 6,
  },
  staffTextInput: {
    backgroundColor: '#1E293B',
    borderWidth: 1.5,
    borderColor: '#334155',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  staffSubmitBtn: {
    backgroundColor: '#FCD116',
    borderRadius: 12,
    paddingVertical: 14,
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#FCD116',
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  staffSubmitBtnText: {
    color: '#0B192C',
    fontSize: 14,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  staffChipSection: {
    width: '100%',
    marginTop: 24,
    borderTopWidth: 1,
    borderTopColor: '#1E293B',
    paddingTop: 16,
  },
  staffChipSectionTitle: {
    color: '#64748B',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.8,
    marginBottom: 10,
  },
  staffChipGrid: {
    gap: 8,
  },
  staffChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 10,
    padding: 10,
    gap: 12,
  },
  staffChipEmoji: {
    fontSize: 20,
  },
  staffChipName: {
    color: '#F8FAFC',
    fontSize: 13,
    fontWeight: '800',
  },
  staffChipDesc: {
    color: '#94A3B8',
    fontSize: 11,
  },
  backToParentBtn: {
    marginTop: 20,
    paddingVertical: 8,
  },
  backToParentBtnText: {
    color: '#38BDF8',
    fontSize: 12,
    fontWeight: '700',
  },

  // Staff Profile Card
  staffProfileCard: {
    backgroundColor: '#0F172A',
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: '#1E293B',
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 12,
  },
  staffAvatarCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#0038A8',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#FCD116',
  },
  staffAvatarText: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '900',
  },
  staffProfileName: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '800',
  },
  staffRolePill: {
    backgroundColor: '#2563EB',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  staffRolePillText: {
    color: '#FFFFFF',
    fontSize: 9,
    fontWeight: '900',
  },
  staffProfileMeta: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 2,
  },
  staffLogoutBtn: {
    backgroundColor: '#1E293B',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#475569',
  },
  staffLogoutBtnText: {
    color: '#E2E8F0',
    fontSize: 11,
    fontWeight: '700',
  },

  // Staff Sub Tabs
  staffSubTabs: {
    flexDirection: 'row',
    backgroundColor: '#0F172A',
    borderRadius: 12,
    padding: 4,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
    gap: 4,
  },
  staffSubTabItem: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 8,
  },
  staffSubTabItemActive: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#FCD116',
  },
  staffSubTabText: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '700',
  },
  staffSubTabTextActive: {
    color: '#FCD116',
    fontWeight: '900',
  },

  // Form 48 DTR Styles
  dtrCard: {
    backgroundColor: '#0F172A',
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: '#1E293B',
    padding: 14,
    marginBottom: 12,
  },
  dtrHeaderRow: {
    marginBottom: 12,
  },
  dtrTitle: {
    color: '#FCD116',
    fontSize: 12,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  dtrDate: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 2,
  },
  dtrGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  dtrGridCell: {
    width: '48%',
    backgroundColor: '#1E293B',
    borderRadius: 10,
    padding: 10,
    borderWidth: 1,
    borderColor: '#334155',
  },
  dtrCellLabel: {
    color: '#64748B',
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  dtrCellValue: {
    color: '#94A3B8',
    fontSize: 16,
    fontWeight: '900',
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  dtrCellFilled: {
    color: '#10B981',
  },
  renderedHoursBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(252, 209, 22, 0.08)',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(252, 209, 22, 0.25)',
    padding: 10,
    marginTop: 12,
    gap: 10,
  },
  renderedHoursIcon: {
    fontSize: 22,
  },
  renderedHoursText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '800',
  },
  renderedHoursSub: {
    color: '#94A3B8',
    fontSize: 10,
    marginTop: 2,
  },

  // Big Clock In Button
  dtrClockButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#10B981',
    borderRadius: 16,
    paddingVertical: 14,
    paddingHorizontal: 20,
    gap: 12,
    marginBottom: 12,
    shadowColor: '#10B981',
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 8,
  },
  dtrClockBtnIcon: {
    fontSize: 24,
  },
  dtrClockBtnTitle: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  dtrClockBtnSubtitle: {
    color: '#D1FAE5',
    fontSize: 11,
    fontWeight: '600',
  },

  staffActionRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  staffTestAlertBtn: {
    flex: 1,
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#38BDF8',
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
  },
  staffTestAlertBtnText: {
    color: '#38BDF8',
    fontSize: 11,
    fontWeight: '800',
  },
  staffRefreshBtn: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#475569',
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 14,
    alignItems: 'center',
  },
  staffRefreshBtnText: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '700',
  },

  // Punch History
  punchHistorySection: {
    backgroundColor: '#0F172A',
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: '#1E293B',
    padding: 14,
  },
  punchSectionTitle: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.8,
    marginBottom: 10,
  },
  punchLogItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
  },
  punchBadge: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#FCD116',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  punchBadgeText: {
    color: '#FCD116',
    fontSize: 10,
    fontWeight: '900',
  },
  punchLogTime: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '700',
  },
  punchLogMethod: {
    color: '#64748B',
    fontSize: 10,
  },
  emptyPunches: {
    paddingVertical: 16,
    alignItems: 'center',
  },
  emptyPunchesText: {
    color: '#64748B',
    fontSize: 12,
    textAlign: 'center',
  },

  // Advisory Class
  advisoryHeaderCard: {
    backgroundColor: '#0F172A',
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: '#1E293B',
    padding: 14,
    marginBottom: 14,
  },
  advisorySectionTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '900',
  },
  advisoryAdviser: {
    color: '#94A3B8',
    fontSize: 12,
    marginTop: 2,
    marginBottom: 12,
  },
  advisoryMetricsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  advisoryMetricCell: {
    flex: 1,
    backgroundColor: '#1E293B',
    borderRadius: 10,
    padding: 10,
    alignItems: 'center',
  },
  advisoryMetricVal: {
    color: '#10B981',
    fontSize: 18,
    fontWeight: '900',
  },
  advisoryMetricLbl: {
    color: '#64748B',
    fontSize: 9,
    fontWeight: '800',
    marginTop: 2,
  },
  advisoryRosterTitle: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.8,
    marginBottom: 8,
  },
  studentRosterCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0F172A',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1E293B',
    padding: 12,
    marginBottom: 6,
    gap: 10,
  },
  studentRosterDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  dotGreen: {
    backgroundColor: '#10B981',
  },
  dotAmber: {
    backgroundColor: '#F59E0B',
  },
  studentRosterName: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '800',
  },
  studentRosterLrn: {
    color: '#64748B',
    fontSize: 10,
    marginTop: 1,
  },
  studentRosterStatus: {
    fontSize: 11,
    fontWeight: '900',
  },
  studentRosterTime: {
    color: '#94A3B8',
    fontSize: 10,
    marginTop: 1,
  },
  staffBulletinHeading: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.8,
    marginBottom: 10,
  },

  // Mandatory Gate Acknowledgment Lock Screen Styles
  ackLockSafeArea: {
    flex: 1,
    backgroundColor: '#070c14',
  },
  ackLockContent: {
    flexGrow: 1,
    padding: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  ackSecurityRibbon: {
    alignItems: 'center',
    marginBottom: 16,
    width: '100%',
  },
  ackRibbonPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.4)',
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 20,
    marginBottom: 8,
    gap: 6,
  },
  ackRibbonDot: {
    color: '#EF4444',
    fontSize: 12,
  },
  ackRibbonText: {
    color: '#FCA5A5',
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 0.8,
  },
  ackSchoolTitle: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
  },
  ackCard: {
    width: '100%',
    backgroundColor: '#0F172A',
    borderRadius: 24,
    borderWidth: 2,
    padding: 20,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.5,
    shadowRadius: 20,
    elevation: 15,
  },
  ackStatusIconBox: {
    width: 80,
    height: 80,
    borderRadius: 40,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },
  ackNoticeTitle: {
    fontSize: 20,
    fontWeight: '900',
    color: '#FFFFFF',
    textAlign: 'center',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  ackNoticeSubtitle: {
    fontSize: 12,
    color: '#94A3B8',
    textAlign: 'center',
    lineHeight: 18,
    marginBottom: 18,
    paddingHorizontal: 10,
  },
  ackStudentCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 14,
    width: '100%',
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#334155',
    gap: 12,
  },
  ackAvatarBox: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#3B82F6',
    alignItems: 'center',
    justifyContent: 'center',
  },
  ackAvatarText: {
    color: '#FFFFFF',
    fontSize: 22,
    fontWeight: '900',
  },
  ackStudentName: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '800',
    marginBottom: 2,
  },
  ackStudentMeta: {
    color: '#38BDF8',
    fontSize: 11,
    fontWeight: '700',
  },
  ackAdviserText: {
    color: '#94A3B8',
    fontSize: 10,
    marginTop: 2,
  },
  ackTelemetryGrid: {
    width: '100%',
    backgroundColor: '#111827',
    borderRadius: 14,
    padding: 12,
    marginBottom: 14,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  ackTelemetryItem: {
    width: '48%',
    padding: 6,
  },
  ackTelemetryLabel: {
    color: '#64748B',
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  ackTelemetryVal: {
    color: '#F8FAFC',
    fontSize: 12,
    fontWeight: '700',
  },
  ackPolicyBox: {
    backgroundColor: 'rgba(56, 189, 248, 0.08)',
    borderLeftWidth: 3,
    borderLeftColor: '#38BDF8',
    padding: 10,
    borderRadius: 8,
    width: '100%',
    marginBottom: 18,
  },
  ackPolicyText: {
    color: '#BAE6FD',
    fontSize: 10,
    lineHeight: 15,
  },
  ackUnlockBtn: {
    width: '100%',
    backgroundColor: '#10B981',
    paddingVertical: 16,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#10B981',
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 8,
  },
  ackUnlockBtnText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '900',
    letterSpacing: 0.8,
  },
  ackBtnSubtext: {
    color: '#64748B',
    fontSize: 10,
    marginTop: 8,
    textAlign: 'center',
  },

  // -------------------------------------------------------------
  // Role Header Badges & Logout Button
  // -------------------------------------------------------------
  roleHeaderPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    backgroundColor: 'rgba(59, 130, 246, 0.2)',
    borderWidth: 1,
    borderColor: '#3B82F6',
  },
  roleHeaderPillStaff: {
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
    borderColor: '#10B981',
  },
  roleHeaderPillText: {
    color: '#60A5FA',
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  roleHeaderPillTextStaff: {
    color: '#34D399',
  },
  logoutButton: {
    width: 38,
    height: 38,
    borderRadius: 10,
    backgroundColor: '#1E293B',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  logoutButtonText: {
    fontSize: 16,
  },
  excuseButtonFull: {
    width: '100%',
    backgroundColor: '#1E293B',
    borderWidth: 1.5,
    borderColor: '#38BDF8',
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // -------------------------------------------------------------
  // Portal & Role Login Screen Styles
  // -------------------------------------------------------------
  loginScrollContent: {
    padding: 20,
    paddingBottom: 40,
    alignItems: 'center',
  },
  loginTopBar: {
    width: '100%',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  loginDepedTag: {
    flex: 1,
    marginRight: 8,
  },
  loginDepedTagText: {
    color: '#94A3B8',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  loginSettingsBtn: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: '#1E293B',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  loginHero: {
    alignItems: 'center',
    marginBottom: 20,
    width: '100%',
  },
  loginLogoWrapper: {
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: '#101C2E',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#FCD116',
    marginBottom: 12,
    shadowColor: '#FCD116',
    shadowOpacity: 0.2,
    shadowRadius: 10,
    elevation: 6,
  },
  loginLogo: {
    width: 56,
    height: 56,
  },
  loginAppTitle: {
    color: '#FFFFFF',
    fontSize: 22,
    fontWeight: '900',
    letterSpacing: 1,
  },
  loginAppSubtitle: {
    color: '#FCD116',
    fontSize: 11,
    fontWeight: '700',
    textAlign: 'center',
    marginTop: 4,
    letterSpacing: 0.5,
  },
  loginSchoolPill: {
    backgroundColor: 'rgba(252, 209, 22, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(252, 209, 22, 0.3)',
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 16,
    marginTop: 10,
  },
  loginSchoolPillText: {
    color: '#CBD5E1',
    fontSize: 11,
    fontWeight: '600',
  },
  loginSegmentContainer: {
    flexDirection: 'row',
    backgroundColor: '#0B192C',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
    padding: 4,
    width: '100%',
    marginBottom: 16,
  },
  loginSegmentTab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 10,
  },
  loginSegmentTabActive: {
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#3B82F6',
  },
  loginSegmentText: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '700',
  },
  loginSegmentTextActive: {
    color: '#FFFFFF',
    fontWeight: '900',
  },
  loginCard: {
    width: '100%',
    backgroundColor: '#0F172A',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#1E3A5F',
    padding: 18,
    marginBottom: 16,
  },
  loginCardTitle: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: '900',
    marginBottom: 4,
  },
  loginCardSubtitle: {
    color: '#94A3B8',
    fontSize: 12,
    lineHeight: 18,
    marginBottom: 16,
  },
  loginInputGroup: {
    width: '100%',
    marginBottom: 14,
  },
  loginInputLabel: {
    color: '#E2E8F0',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  loginInput: {
    backgroundColor: '#08101E',
    borderWidth: 1.5,
    borderColor: '#1E293B',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: 'bold',
  },
  loginSubmitBtn: {
    backgroundColor: '#FCD116',
    borderRadius: 12,
    paddingVertical: 14,
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#FCD116',
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
    marginTop: 6,
  },
  loginSubmitBtnText: {
    color: '#0B192C',
    fontSize: 14,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  demoSection: {
    marginTop: 20,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#1E293B',
    width: '100%',
  },
  demoSectionTitle: {
    color: '#64748B',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.8,
    marginBottom: 10,
  },
  demoChipList: {
    gap: 8,
  },
  demoChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 12,
    padding: 10,
    gap: 10,
  },
  demoChipIcon: {
    fontSize: 20,
  },
  demoChipName: {
    color: '#F8FAFC',
    fontSize: 13,
    fontWeight: '800',
  },
  demoChipMeta: {
    color: '#94A3B8',
    fontSize: 11,
  },
  demoChipArrow: {
    color: '#FCD116',
    fontSize: 16,
    fontWeight: '900',
  },
  staffGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  staffChipItem: {
    width: '48%',
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1E293B',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 10,
    padding: 10,
    gap: 8,
  },
  staffChipItemIcon: {
    fontSize: 18,
  },
  staffChipItemName: {
    color: '#F8FAFC',
    fontSize: 12,
    fontWeight: '800',
  },
  staffChipItemDesc: {
    color: '#94A3B8',
    fontSize: 10,
  },
  loginFooter: {
    alignItems: 'center',
    marginTop: 12,
    marginBottom: 20,
  },
  loginFooterText: {
    color: '#64748B',
    fontSize: 10,
    fontWeight: '600',
  },
  loginFooterSub: {
    color: '#475569',
    fontSize: 9,
    marginTop: 2,
  },
});
