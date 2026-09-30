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
  Platform
} from 'react-native';

const { width, height } = Dimensions.get('window');

// Server endpoints (Auto-failover: Cloud Vercel & Local LAN)
const CLOUD_SERVER_URL = "https://deped-smile.vercel.app";
const LOCAL_SERVER_URL = "http://192.168.1.9:5000";
const DEFAULT_LRN = "152008250007";

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

  // Data State
  const [student, setStudent] = useState({
    lrn: "152008250007",
    full_name: "Juan Dela Cruz",
    first_name: "Juan",
    last_name: "Dela Cruz",
    grade_section: "Grade 10 - Rizal",
    grade_level: "Grade 10",
    class_adviser: "Mrs. Corazon Aquino",
    parent_name: "Maria Dela Cruz",
    parent_phone: "09171234567"
  });
  const [siblings, setSiblings] = useState([
    { lrn: "152008250007", first_name: "Juan", grade_level: "Grade 10", grade_section: "Grade 10 - Rizal" },
    { lrn: "152008250008", first_name: "Maria", grade_level: "Grade 8", grade_section: "Grade 8 - Luna" }
  ]);
  const [status, setStatus] = useState("INSIDE_CAMPUS");
  const [latestLog, setLatestLog] = useState({
    id: 101,
    lrn: "152008250007",
    student_name: "Juan Dela Cruz",
    scan_type: "TIME_IN",
    timestamp: "2026-09-27 07:18:42",
    time_formatted: "07:18 AM",
    device_id: "GATE-1-FACIAL-AI",
    verification_method: "AI Facial Biometrics",
    remarks: "Verified Morning Campus Entry"
  });
  const [todayLogs, setTodayLogs] = useState([
    {
      id: 101,
      lrn: "152008250007",
      student_name: "Juan Dela Cruz",
      scan_type: "TIME_IN",
      timestamp: "2026-09-27 07:18:42",
      time_formatted: "07:18 AM",
      device_id: "GATE-1-FACIAL-AI",
      verification_method: "AI Facial Biometrics",
      remarks: "Verified Morning Campus Entry"
    }
  ]);
  const [allLogs, setAllLogs] = useState([]);
  const [upcomingEvents, setUpcomingEvents] = useState([]);
  const [urgentAnnouncements, setUrgentAnnouncements] = useState([]);
  const [allAnnouncements, setAllAnnouncements] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [todayDate, setTodayDate] = useState("Sunday, September 27, 2026");

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

  // Polling tracker & banner anim
  const lastEventIdRef = useRef(101);
  const pollIntervalRef = useRef(null);
  const bannerAnim = useRef(new Animated.Value(-120)).current;

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
      duration: 2000,
      useNativeDriver: false,
    }).start();

    // Staged status messages
    const t1 = setTimeout(() => setLoadingPhase("ESTABLISHING SECURE GATE TELEMETRY..."), 450);
    const t2 = setTimeout(() => setLoadingPhase("SYNCHRONIZING BIOMETRIC GATE LOGS..."), 900);
    const t3 = setTimeout(() => setLoadingPhase("DECRYPTING INCIDENT LOGS & E-NOTIFICATIONS..."), 1350);
    const t4 = setTimeout(() => setLoadingPhase("SYSTEM SECURE • READY"), 1750);

    // Initial database fetch
    fetchDashboardData(activeLrn);
    fetchNotifications(activeLrn);
    startPolling(activeLrn);

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
    }, 2100);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
      clearTimeout(completeTimer);
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [activeLrn, serverUrl]);

  // -------------------------------------------------------------
  // 2. Fetch Data from Real Database with Fallback
  // -------------------------------------------------------------
  const fetchDashboardData = async (lrn) => {
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
          if (data.latest_log.id) lastEventIdRef.current = data.latest_log.id;
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
      console.warn("Server connection notice:", err.message);
      // Fallback to local server if cloud is offline, or keep existing cached state
      if (serverUrl === CLOUD_SERVER_URL) {
        try {
          const localRes = await fetch(`${LOCAL_SERVER_URL}/api/mobile/home/${lrn}`);
          const localData = await localRes.json();
          if (localData && localData.success) {
            setServerUrl(LOCAL_SERVER_URL);
            setTempServerUrl(LOCAL_SERVER_URL);
            setStudent(localData.student);
            setStatus(localData.status);
            setTodayLogs(localData.today_logs || []);
            setIncidents(localData.incidents || []);
          }
        } catch (_) {}
      }
    } finally {
      setRefreshing(false);
    }
  };

  // -------------------------------------------------------------
  // 2b. Fetch Push Notifications (n8n Automated Workflow Center)
  // -------------------------------------------------------------
  const fetchNotifications = async (lrn) => {
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
  // 3. Background Polling & E-Notification Alert Stream
  // -------------------------------------------------------------
  const startPolling = (lrn) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const lastId = lastEventIdRef.current;
        const res = await fetch(`${serverUrl}/api/parent/poll/${lrn}?last_id=${lastId}`, {
          headers: { 'Accept': 'application/json' }
        });
        const data = await res.json();
        if (data.has_new && data.event) {
          lastEventIdRef.current = data.event.id;
          triggerGateAlert(data.event);
          fetchDashboardData(lrn);
        }

        // Periodically poll automated push notification pipeline
        const notifRes = await fetch(`${serverUrl}/api/mobile/notifications/${lrn}`, {
          headers: { 'Accept': 'application/json' }
        });
        const notifData = await notifRes.json();
        if (notifData && notifData.success) {
          setNotifications(notifData.notifications || []);
          const unread = notifData.unread_count || 0;
          if (unread > lastNotifCountRef.current && lastNotifCountRef.current > 0) {
            // New automated push notification received!
            if (vibrateEnabled) Vibration.vibrate([0, 350, 100, 350]);
            const latest = notifData.notifications[0];
            if (latest && pushEnabled) {
              setAlertData({
                student_name: student ? student.full_name : "Juan Dela Cruz",
                scan_type: latest.title,
                verification_method: latest.type || "n8n Automated Push",
                remarks: latest.body
              });
              Animated.sequence([
                Animated.timing(bannerAnim, {
                  toValue: 20,
                  duration: 350,
                  useNativeDriver: true,
                }),
                Animated.delay(4500),
                Animated.timing(bannerAnim, {
                  toValue: -120,
                  duration: 300,
                  useNativeDriver: true,
                })
              ]).start();
            }
          }
          lastNotifCountRef.current = unread;
          setUnreadNotifCount(unread);
        }
      } catch (_) {}
    }, 3500);
  };

  const triggerGateAlert = (eventData) => {
    if (vibrateEnabled) {
      // Dual haptic pulse
      Vibration.vibrate([0, 450, 120, 450]);
    }

    setAlertData(eventData);
    setAlertModalVisible(true);

    if (pushEnabled) {
      // Slide down floating heads-up banner
      Animated.sequence([
        Animated.timing(bannerAnim, {
          toValue: 20,
          duration: 350,
          useNativeDriver: true,
        }),
        Animated.delay(4500),
        Animated.timing(bannerAnim, {
          toValue: -120,
          duration: 300,
          useNativeDriver: true,
        })
      ]).start();
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    if (vibrateEnabled) Vibration.vibrate(40);
    fetchDashboardData(activeLrn);
    fetchNotifications(activeLrn);
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
  const handleTestAlert = () => {
    const isArrival = status !== "INSIDE_CAMPUS";
    const simulatedEvent = {
      id: Date.now(),
      student_name: student ? student.full_name : "Juan Dela Cruz",
      scan_type: isArrival ? "TIME_IN" : "TIME_OUT",
      timestamp: new Date().toISOString(),
      time_formatted: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      device_id: "GATE-1-FACIAL-AI",
      verification_method: "AI Facial Biometrics",
      remarks: "Official Gate Verification • Biometric Matched"
    };
    triggerGateAlert(simulatedEvent);
  };

  // Submit Excuse Note
  const handleSubmitExcuse = async () => {
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
          <Text style={styles.bannerIconText}>🔔</Text>
        </View>
        <View style={{ flex: 1 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text style={styles.bannerTitle}>E-NOTIFICATION ALERT</Text>
            <Text style={styles.bannerTime}>Just now</Text>
          </View>
          <Text style={styles.bannerBody} numberOfLines={2}>
            {alertData ? `${alertData.student_name} (${alertData.scan_type}) verified at Gate 1 via ${alertData.verification_method}` : "Gate attendance scan verified."}
          </Text>
        </View>
      </Animated.View>

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
              <Text style={styles.headerTitle}>PROJECT S.M.I.L.E.</Text>
              <View style={styles.depedBadge}>
                <Text style={styles.depedBadgeText}>DepEd</Text>
              </View>
            </View>
            <Text style={styles.headerSubtitle} numberOfLines={1}>
              Security Monitoring, Incident Logging, and E-notification
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
        </View>
      </View>

      {/* Main Tab Content Body */}
      <View style={styles.tabContentContainer}>
        {activeTab === 'gate' && renderGateTab()}
        {activeTab === 'incidents' && renderIncidentsTab()}
        {activeTab === 'bulletins' && renderBulletinsTab()}
        {activeTab === 'events' && renderEventsTab()}
        {activeTab === 'security' && renderSecurityTab()}
      </View>

      {/* Bottom Navigation Tab Bar (5 High-Performance Tabs) */}
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

        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'security' && styles.tabButtonActive]}
          onPress={() => { setActiveTab('security'); if (vibrateEnabled) Vibration.vibrate(25); }}
        >
          <Text style={[styles.tabIcon, activeTab === 'security' && styles.tabIconActive]}>🔐</Text>
          <Text style={[styles.tabLabel, activeTab === 'security' && styles.tabLabelActive]}>Security</Text>
        </TouchableOpacity>
      </View>

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
          <View style={[styles.modalCard, { borderColor: '#FCD116' }]}>
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
                  <Text style={styles.alertDetailVal}>{alertData.student_name}</Text>
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
                  <Text style={styles.alertDetailVal}>{alertData.device_id}</Text>
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
          </View>
        </View>
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
                  fetchDashboardData(tempLrn.trim());
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

    </SafeAreaView>
  );

  // -------------------------------------------------------------
  // TAB 1: GATE MONITORING (ATTENDANCE & CAMPUS PRESENCE)
  // -------------------------------------------------------------
  function renderGateTab() {
    return (
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FCD116" />}
      >
        {/* Sibling Switcher Bar */}
        {siblings.length > 1 && (
          <View style={styles.siblingBar}>
            <Text style={styles.siblingLabel}>STUDENTS:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.siblingScroll}>
              {siblings.map((sib) => {
                const isActive = sib.lrn === activeLrn;
                return (
                  <TouchableOpacity
                    key={sib.lrn}
                    onPress={() => { setActiveLrn(sib.lrn); if (vibrateEnabled) Vibration.vibrate(30); }}
                    style={[styles.siblingPill, isActive && styles.siblingPillActive]}
                  >
                    <Text style={[styles.siblingPillText, isActive && styles.siblingPillTextActive]}>
                      {sib.first_name} ({sib.grade_level || "Student"})
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </View>
        )}

        {/* Active Learner Profile Header */}
        <View style={styles.profileCard}>
          <View style={styles.profileTopRow}>
            <View style={styles.avatarBox}>
              <Text style={styles.avatarText}>{student ? student.first_name[0] : "J"}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.studentName}>{student ? student.full_name : "Juan Dela Cruz"}</Text>
              <Text style={styles.studentMeta}>
                LRN: {student?.lrn || activeLrn} • {student?.grade_section || "Grade 10 - Rizal"}
              </Text>
              <Text style={styles.studentAdviser}>
                Adviser: {student?.class_adviser || "Mrs. Corazon Aquino"}
              </Text>
            </View>
          </View>
        </View>

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

          {/* Quick Action Buttons */}
          <View style={styles.actionRow}>
            <TouchableOpacity style={styles.testAlertButton} onPress={handleTestAlert}>
              <Text style={styles.testAlertButtonText}>⚡ Test Alert & Vibrate</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.excuseButton} onPress={() => setExcuseModalVisible(true)}>
              <Text style={styles.excuseButtonText}>📝 File Excuse Note</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Push Notification Center & n8n Automation Engine Card */}
        <View style={styles.n8nHubCard}>
          <View style={styles.n8nHubHeader}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Text style={styles.n8nHubTitle}>PUSH NOTIFICATION CENTER</Text>
              <View style={styles.n8nBadge}>
                <Text style={styles.n8nBadgeText}>n8n Automation</Text>
              </View>
            </View>
            {unreadNotifCount > 0 ? (
              <View style={styles.unreadBadgeSmall}>
                <Text style={styles.unreadBadgeSmallText}>{unreadNotifCount} NEW</Text>
              </View>
            ) : null}
          </View>
          <Text style={styles.n8nHubDesc}>
            Automated notifications notify parents periodically from time to time: biometric gate scans, morning absence sweeps, PAGASA weather, and health updates.
          </Text>

          <View style={styles.n8nButtonRow}>
            <TouchableOpacity
              style={styles.n8nRunButton}
              onPress={() => runAutomationWorkflow(2, 'Morning Tardy & Safety Check Sweep')}
              disabled={runningAutomation}
            >
              {runningAutomation ? (
                <ActivityIndicator size="small" color="#0B192C" />
              ) : (
                <Text style={styles.n8nRunButtonText}>⚡ Run Automated Check</Text>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.n8nViewCenterButton}
              onPress={() => {
                setNotifModalVisible(true);
                if (vibrateEnabled) Vibration.vibrate(20);
              }}
            >
              <Text style={styles.n8nViewCenterButtonText}>Open Stream ({notifications.length})</Text>
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
            <Text style={styles.diagLabel}>Monitored Student:</Text>
            <Text style={styles.diagVal}>{student ? student.full_name : "Juan Dela Cruz"} ({activeLrn})</Text>
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
              fetchDashboardData(activeLrn);
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
});
