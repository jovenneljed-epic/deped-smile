import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
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

const { width } = Dimensions.get('window');

// Default Cloud Backend & Initial Student
const DEFAULT_SERVER_URL = "https://deped-smile.vercel.app";
const DEFAULT_LRN = "152008250007";

export default function App() {
  const [serverUrl, setServerUrl] = useState(DEFAULT_SERVER_URL);
  const [activeLrn, setActiveLrn] = useState(DEFAULT_LRN);
  const [student, setStudent] = useState(null);
  const [siblings, setSiblings] = useState([]);
  const [status, setStatus] = useState("AWAITING_ARRIVAL");
  const [latestLog, setLatestLog] = useState(null);
  const [todayLogs, setTodayLogs] = useState([]);
  const [upcomingEvents, setUpcomingEvents] = useState([]);
  const [urgentAnnouncements, setUrgentAnnouncements] = useState([]);
  const [todayDate, setTodayDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Modals
  const [excuseModalVisible, setExcuseModalVisible] = useState(false);
  const [settingsModalVisible, setSettingsModalVisible] = useState(false);
  const [alertModalVisible, setAlertModalVisible] = useState(false);
  const [alertData, setAlertData] = useState(null);

  // Excuse Form State
  const [excuseReason, setExcuseReason] = useState("Illness / Medical");
  const [excuseDate, setExcuseDate] = useState(new Date().toISOString().split('T')[0]);
  const [excuseDetails, setExcuseDetails] = useState("");
  const [submittingExcuse, setSubmittingExcuse] = useState(false);

  // Settings State
  const [tempServerUrl, setTempServerUrl] = useState(DEFAULT_SERVER_URL);
  const [tempLrn, setTempLrn] = useState(DEFAULT_LRN);

  // Polling tracker
  const lastEventIdRef = useRef(0);
  const pollIntervalRef = useRef(null);

  // Alert Banner Animation
  const bannerAnim = useRef(new Animated.Value(-100)).current;

  // 1. Initial Load & Polling Lifecycle
  useEffect(() => {
    fetchDashboardData(activeLrn);
    startPolling(activeLrn);

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [activeLrn, serverUrl]);

  // Fetch complete mobile dashboard
  const fetchDashboardData = async (lrn) => {
    try {
      const res = await fetch(`${serverUrl}/api/mobile/home/${lrn}`, {
        headers: { 'Accept': 'application/json' }
      });
      const data = await res.json();
      if (data.success) {
        setStudent(data.student);
        setSiblings(data.siblings || [data.student]);
        setStatus(data.status || "AWAITING_ARRIVAL");
        setLatestLog(data.latest_log || null);
        setTodayLogs(data.today_logs || []);
        setUpcomingEvents(data.upcoming_events || []);
        setUrgentAnnouncements(data.urgent_announcements || []);
        setTodayDate(data.today_date || "");
        if (data.latest_log && data.latest_log.id) {
          lastEventIdRef.current = data.latest_log.id;
        }
      }
    } catch (err) {
      console.warn("Could not fetch cloud dashboard:", err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Background Poller for real-time gate kiosk scans
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
      } catch (e) {
        // Silent poll error handling
      }
    }, 3000);
  };

  // Trigger Native Vibration & Alert UI
  const triggerGateAlert = (eventData) => {
    // Native phone vibration: pattern [pause, vibrate, pause, vibrate]
    Vibration.vibrate([0, 500, 150, 500]);

    setAlertData(eventData);
    setAlertModalVisible(true);

    // Slide down floating notification banner
    Animated.sequence([
      Animated.timing(bannerAnim, {
        toValue: 20,
        duration: 350,
        useNativeDriver: true,
      }),
      Animated.delay(4000),
      Animated.timing(bannerAnim, {
        toValue: -120,
        duration: 300,
        useNativeDriver: true,
      })
    ]).start();
  };

  const onRefresh = () => {
    setRefreshing(true);
    fetchDashboardData(activeLrn);
  };

  // Test simulation button
  const handleTestAlert = () => {
    const isArrival = status !== "INSIDE_CAMPUS";
    const simulatedEvent = {
      id: Date.now(),
      student_name: student ? student.full_name : "Juan Dela Cruz",
      scan_type: isArrival ? "TIME_IN" : "TIME_OUT",
      timestamp: new Date().toISOString(),
      time_formatted: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      device_id: "GATE-1-SMART-ID",
      verification_method: "AI Face Recognition",
      remarks: "Official Gate Verification"
    };
    triggerGateAlert(simulatedEvent);
  };

  // Submit Excuse Letter
  const handleSubmitExcuse = async () => {
    if (!excuseDetails.trim()) {
      Alert.alert("Missing Details", "Please provide a brief explanation for the excuse letter.");
      return;
    }
    setSubmittingExcuse(true);
    try {
      const res = await fetch(`${serverUrl}/api/parent/excuse-note`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lrn: activeLrn,
          parent_name: student?.parent_name || "Parent",
          parent_phone: student?.parent_phone || "",
          date_effective: excuseDate,
          reason: excuseReason,
          details: excuseDetails.trim()
        })
      });
      const data = await res.json();
      if (data.success) {
        Alert.alert("Submitted Successfully", "Your excuse letter has been filed with the class adviser.");
        setExcuseModalVisible(false);
        setExcuseDetails("");
      } else {
        Alert.alert("Submission Failed", data.message || "Could not save excuse letter.");
      }
    } catch (err) {
      Alert.alert("Connection Error", err.message);
    } finally {
      setSubmittingExcuse(false);
    }
  };

  // Save Settings
  const handleSaveSettings = () => {
    const cleanUrl = tempServerUrl.replace(/\/+$/, '');
    setServerUrl(cleanUrl);
    setActiveLrn(tempLrn.trim());
    setSettingsModalVisible(false);
    setLoading(true);
  };

  if (loading && !student) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#FCD116" />
        <Text style={styles.loadingText}>Connecting to DepEd S.M.I.L.E. Cloud...</Text>
        <Text style={styles.loadingSubtext}>{serverUrl}</Text>
      </View>
    );
  }

  const isInside = status === "INSIDE_CAMPUS";
  const isExited = status === "SAFELY_EXITED";

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0B192C" />

      {/* Slide-Down Native Notification Banner */}
      <Animated.View style={[styles.floatingBanner, { transform: [{ translateY: bannerAnim }] }]}>
        <View style={styles.bannerIconBox}>
          <Text style={styles.bannerIconText}>🔔</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.bannerTitle}>DepEd Gate Alert Verified</Text>
          <Text style={styles.bannerBody} numberOfLines={2}>
            {alertData ? `${alertData.student_name} (${alertData.scan_type === "TIME_IN" ? "Entered" : "Safely Exited"} Gate 1 at ${alertData.time_formatted || "Just Now"})` : "New Attendance Transaction"}
          </Text>
        </View>
      </Animated.View>

      {/* Top Header */}
      <View style={styles.header}>
        <View style={styles.headerBrand}>
          <View style={styles.depedBadge}>
            <Text style={styles.depedBadgeText}>DepEd</Text>
          </View>
          <View>
            <Text style={styles.headerTitle}>PROJECT S.M.I.L.E.</Text>
            <Text style={styles.headerSubtitle}>Parent Safety Mobile Companion</Text>
          </View>
        </View>
        <TouchableOpacity style={styles.settingsButton} onPress={() => setSettingsModalVisible(true)}>
          <Text style={styles.settingsButtonText}>⚙️</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#FCD116" />}
      >

        {/* Sibling Switcher Bar */}
        {siblings.length > 1 && (
          <View style={styles.siblingBar}>
            <Text style={styles.siblingLabel}>CHILDREN:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.siblingScroll}>
              {siblings.map((sib) => {
                const isActive = sib.lrn === activeLrn;
                return (
                  <TouchableOpacity
                    key={sib.lrn}
                    onPress={() => setActiveLrn(sib.lrn)}
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
              <Text style={styles.avatarText}>{student ? student.first_name[0] : "S"}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.studentName}>{student ? student.full_name : "Learner"}</Text>
              <Text style={styles.studentMeta}>
                LRN: {student?.lrn || activeLrn} • {student?.grade_section || "Enrolled Learner"}
              </Text>
              <Text style={styles.studentAdviser}>
                Adviser: {student?.class_adviser || "Class Adviser"}
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
              : "No gate transactions recorded today yet."}
          </Text>

          {/* Quick Action Buttons */}
          <View style={styles.actionRow}>
            <TouchableOpacity style={styles.testAlertButton} onPress={handleTestAlert}>
              <Text style={styles.testAlertButtonText}>⚡ Test Alert Chime & Vibrate</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.excuseButton} onPress={() => setExcuseModalVisible(true)}>
              <Text style={styles.excuseButtonText}>📝 File Excuse Letter</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Today's Gate Attendance Timeline */}
        <View style={styles.sectionContainer}>
          <View style={styles.sectionHeaderRow}>
            <Text style={styles.sectionTitle}>TODAY'S GATE SCANS</Text>
            <Text style={styles.sectionMeta}>{todayDate || "Official PST"}</Text>
          </View>

          {todayLogs.length === 0 ? (
            <View style={styles.emptyCard}>
              <Text style={styles.emptyTitle}>No scans recorded today</Text>
              <Text style={styles.emptySub}>Transactions will appear here in real-time as student scans at the school gate.</Text>
            </View>
          ) : (
            todayLogs.map((log) => {
              const isIn = log.scan_type === "TIME_IN";
              return (
                <View key={log.id} style={styles.logCard}>
                  <View style={[styles.logTypeBadge, isIn ? styles.badgeIn : styles.badgeOut]}>
                    <Text style={[styles.badgeText, isIn ? styles.badgeTextIn : styles.badgeTextOut]}>
                      {isIn ? "TIME-IN" : "TIME-OUT"}
                    </Text>
                  </View>
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={styles.logTime}>{log.time_formatted || log.timestamp}</Text>
                    <Text style={styles.logDevice}>
                      {log.device_id || "Gate 1"} • {log.verification_method || "Face Scan"}
                    </Text>
                  </View>
                  <Text style={styles.logCheckmark}>✓</Text>
                </View>
              );
            })
          )}
        </View>

        {/* Urgent School Bulletins & Announcements */}
        {urgentAnnouncements.length > 0 && (
          <View style={styles.sectionContainer}>
            <Text style={styles.sectionTitle}>⚠️ OFFICIAL SCHOOL BULLETINS</Text>
            {urgentAnnouncements.map((ann) => (
              <View key={ann.id} style={styles.bulletinCard}>
                <Text style={styles.bulletinTitle}>{ann.title}</Text>
                <Text style={styles.bulletinContent}>{ann.content}</Text>
                <Text style={styles.bulletinMeta}>DepEd Advisory • {ann.author || "School Administration"}</Text>
              </View>
            ))}
          </View>
        )}

        {/* School Events Calendar */}
        {upcomingEvents.length > 0 && (
          <View style={styles.sectionContainer}>
            <Text style={styles.sectionTitle}>📅 UPCOMING SCHOOL EVENTS</Text>
            {upcomingEvents.map((ev) => (
              <View key={ev.id} style={styles.eventCard}>
                <View style={styles.eventDateBox}>
                  <Text style={styles.eventMonth}>{ev.short_month || "OCT"}</Text>
                  <Text style={styles.eventDay}>{ev.day_num || "08"}</Text>
                </View>
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <Text style={styles.eventTitle}>{ev.title}</Text>
                  <Text style={styles.eventTime}>{ev.start_time} - {ev.end_time} • {ev.location}</Text>
                  <Text style={styles.eventTarget}>{ev.target_grades}</Text>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Footer info */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>DepEd Project S.M.I.L.E. • Don Montano CIS</Text>
          <Text style={styles.footerSub}>Connected to Cloud: {serverUrl}</Text>
        </View>

      </ScrollView>

      {/* MODAL: Excuse Letter Submission */}
      <Modal visible={excuseModalVisible} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <Text style={styles.modalHeader}>File Excuse Letter</Text>
            <Text style={styles.modalSub}>Sends notice directly to {student?.class_adviser || "Class Adviser"}</Text>

            <Text style={styles.inputLabel}>REASON FOR ABSENCE / TARDINESS</Text>
            <View style={styles.reasonRow}>
              {["Illness / Medical", "Family Emergency", "Severe Weather", "Personal"].map((r) => (
                <TouchableOpacity
                  key={r}
                  style={[styles.reasonPill, excuseReason === r && styles.reasonPillActive]}
                  onPress={() => setExcuseReason(r)}
                >
                  <Text style={[styles.reasonText, excuseReason === r && styles.reasonTextActive]}>{r}</Text>
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

            <Text style={styles.inputLabel}>DETAILS & EXPLANATION</Text>
            <TextInput
              style={[styles.textInput, { height: 80, textAlignVertical: 'top' }]}
              value={excuseDetails}
              onChangeText={setExcuseDetails}
              placeholder="Provide reason and medical / parent notes..."
              placeholderTextColor="#64748B"
              multiline
            />

            <View style={styles.modalButtonRow}>
              <TouchableOpacity
                style={styles.cancelModalBtn}
                onPress={() => setExcuseModalVisible(false)}
                disabled={submittingExcuse}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.submitModalBtn}
                onPress={handleSubmitExcuse}
                disabled={submittingExcuse}
              >
                {submittingExcuse ? (
                  <ActivityIndicator color="#0B192C" />
                ) : (
                  <Text style={styles.submitBtnText}>Submit to Adviser</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* MODAL: Cloud Server Settings */}
      <Modal visible={settingsModalVisible} animationType="fade" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <Text style={styles.modalHeader}>App & Server Settings</Text>
            <Text style={styles.modalSub}>Configure your school's live Project S.M.I.L.E. cloud endpoint</Text>

            <Text style={styles.inputLabel}>SERVER BACKEND URL</Text>
            <TextInput
              style={styles.textInput}
              value={tempServerUrl}
              onChangeText={setTempServerUrl}
              autoCapitalize="none"
              placeholder="https://deped-smile.vercel.app"
              placeholderTextColor="#64748B"
            />

            <Text style={styles.inputLabel}>STUDENT LRN</Text>
            <TextInput
              style={styles.textInput}
              value={tempLrn}
              onChangeText={setTempLrn}
              keyboardType="number-pad"
              placeholder="152008250007"
              placeholderTextColor="#64748B"
            />

            <View style={styles.modalButtonRow}>
              <TouchableOpacity style={styles.cancelModalBtn} onPress={() => setSettingsModalVisible(false)}>
                <Text style={styles.cancelBtnText}>Close</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.submitModalBtn} onPress={handleSaveSettings}>
                <Text style={styles.submitBtnText}>Save & Connect</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* MODAL: Real-Time Gate Scan Notification Popup */}
      <Modal visible={alertModalVisible} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalBox, { backgroundColor: '#0B192C', borderColor: '#FCD116', borderWidth: 2 }]}>
            <View style={styles.alertHeaderRow}>
              <Text style={{ fontSize: 24 }}>🔔</Text>
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={{ fontSize: 16, fontWeight: 'bold', color: '#FCD116' }}>REAL-TIME GATE SCAN</Text>
                <Text style={{ fontSize: 11, color: '#94A3B8' }}>Verified DepEd Attendance Transaction</Text>
              </View>
            </View>

            {alertData && (
              <View style={styles.alertDetailBox}>
                <Text style={styles.alertStudentName}>{alertData.student_name}</Text>
                <View style={[
                  styles.alertBadge,
                  alertData.scan_type === "TIME_IN" ? styles.badgeIn : styles.badgeOut
                ]}>
                  <Text style={[
                    styles.alertBadgeText,
                    alertData.scan_type === "TIME_IN" ? styles.badgeTextIn : styles.badgeTextOut
                  ]}>
                    {alertData.scan_type === "TIME_IN" ? "TIME-IN (CAMPUS ENTRY)" : "TIME-OUT (CAMPUS DEPARTURE)"}
                  </Text>
                </View>
                <Text style={styles.alertTimestamp}>Time: {alertData.time_formatted || "Just Now"}</Text>
                <Text style={styles.alertDevice}>{alertData.device_id || "School Gate 1"} • {alertData.verification_method || "Biometrics"}</Text>
              </View>
            )}

            <TouchableOpacity style={styles.dismissBtn} onPress={() => setAlertModalVisible(false)}>
              <Text style={styles.dismissBtnText}>Acknowledge & Close</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#070D18',
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#070D18',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  loadingText: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: 'bold',
    marginTop: 16,
  },
  loadingSubtext: {
    color: '#64748B',
    fontSize: 12,
    marginTop: 6,
  },
  floatingBanner: {
    position: 'absolute',
    top: 50,
    left: 16,
    right: 16,
    zIndex: 9999,
    backgroundColor: '#0F172A',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#38BDF8',
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.4,
    shadowRadius: 10,
    elevation: 8,
  },
  bannerIconBox: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: 'rgba(56, 189, 248, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  bannerIconText: {
    fontSize: 18,
  },
  bannerTitle: {
    color: '#38BDF8',
    fontSize: 12,
    fontWeight: 'bold',
  },
  bannerBody: {
    color: '#F8FAFC',
    fontSize: 12,
    marginTop: 2,
  },
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
    gap: 10,
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
  headerTitle: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  headerSubtitle: {
    color: '#94A3B8',
    fontSize: 10,
  },
  settingsButton: {
    padding: 8,
    borderRadius: 10,
    backgroundColor: '#1E293B',
  },
  settingsButtonText: {
    fontSize: 16,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  siblingBar: {
    marginBottom: 12,
  },
  siblingLabel: {
    color: '#94A3B8',
    fontSize: 10,
    fontWeight: 'bold',
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
    backgroundColor: '#0038A8',
    borderColor: '#38BDF8',
  },
  siblingPillText: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '600',
  },
  siblingPillTextActive: {
    color: '#FFFFFF',
    fontWeight: 'bold',
  },
  profileCard: {
    backgroundColor: '#0F172A',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: '#1E293B',
    marginBottom: 12,
  },
  profileTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatarBox: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#0038A8',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  avatarText: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: 'bold',
  },
  studentName: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: 'bold',
  },
  studentMeta: {
    color: '#FCD116',
    fontSize: 11,
    fontWeight: '600',
    marginTop: 2,
  },
  studentAdviser: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 2,
  },
  statusCard: {
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    marginBottom: 16,
  },
  statusCardInside: {
    backgroundColor: 'rgba(6, 78, 59, 0.4)',
    borderColor: '#10B981',
  },
  statusCardExited: {
    backgroundColor: 'rgba(30, 58, 138, 0.4)',
    borderColor: '#3B82F6',
  },
  statusCardAwaiting: {
    backgroundColor: 'rgba(120, 53, 15, 0.3)',
    borderColor: '#F59E0B',
  },
  statusIndicatorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 8,
  },
  statusDotGreen: { backgroundColor: '#10B981' },
  statusDotBlue: { backgroundColor: '#3B82F6' },
  statusDotYellow: { backgroundColor: '#F59E0B' },
  statusHeading: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  statusTimestamp: {
    color: '#CBD5E1',
    fontSize: 12,
    lineHeight: 18,
  },
  actionRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 14,
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
    fontWeight: 'bold',
  },
  excuseButton: {
    flex: 1,
    backgroundColor: '#1E293B',
    paddingVertical: 10,
    borderRadius: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#475569',
  },
  excuseButtonText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: 'bold',
  },
  sectionContainer: {
    marginBottom: 16,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  sectionTitle: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 0.8,
  },
  sectionMeta: {
    color: '#64748B',
    fontSize: 10,
  },
  emptyCard: {
    backgroundColor: '#0F172A',
    borderRadius: 14,
    padding: 16,
    alignItems: 'center',
  },
  emptyTitle: {
    color: '#94A3B8',
    fontSize: 13,
    fontWeight: 'bold',
  },
  emptySub: {
    color: '#64748B',
    fontSize: 11,
    textAlign: 'center',
    marginTop: 4,
  },
  logCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0F172A',
    borderRadius: 14,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  logTypeBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  badgeIn: { backgroundColor: 'rgba(16, 185, 129, 0.2)' },
  badgeOut: { backgroundColor: 'rgba(59, 130, 246, 0.2)' },
  badgeText: { fontSize: 10, fontWeight: '900' },
  badgeTextIn: { color: '#34D399' },
  badgeTextOut: { color: '#60A5FA' },
  logTime: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: 'bold',
  },
  logDevice: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 2,
  },
  logCheckmark: {
    color: '#10B981',
    fontSize: 14,
    fontWeight: 'bold',
  },
  bulletinCard: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderColor: 'rgba(239, 68, 68, 0.3)',
    borderWidth: 1,
    borderRadius: 14,
    padding: 14,
    marginBottom: 8,
  },
  bulletinTitle: {
    color: '#FCA5A5',
    fontSize: 13,
    fontWeight: 'bold',
  },
  bulletinContent: {
    color: '#E2E8F0',
    fontSize: 12,
    marginTop: 4,
    lineHeight: 18,
  },
  bulletinMeta: {
    color: '#94A3B8',
    fontSize: 10,
    marginTop: 6,
  },
  eventCard: {
    flexDirection: 'row',
    backgroundColor: '#0F172A',
    borderRadius: 14,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#1E293B',
    alignItems: 'center',
  },
  eventDateBox: {
    width: 44,
    height: 44,
    borderRadius: 10,
    backgroundColor: '#0038A8',
    justifyContent: 'center',
    alignItems: 'center',
  },
  eventMonth: {
    color: '#FCD116',
    fontSize: 9,
    fontWeight: '900',
  },
  eventDay: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '900',
  },
  eventTitle: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: 'bold',
  },
  eventTime: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 2,
  },
  eventTarget: {
    color: '#64748B',
    fontSize: 10,
    marginTop: 2,
  },
  footer: {
    marginTop: 20,
    alignItems: 'center',
    paddingVertical: 12,
  },
  footerText: {
    color: '#64748B',
    fontSize: 11,
    fontWeight: 'bold',
  },
  footerSub: {
    color: '#475569',
    fontSize: 10,
    marginTop: 2,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalBox: {
    width: '100%',
    backgroundColor: '#0F172A',
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: '#334155',
  },
  modalHeader: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: 'bold',
  },
  modalSub: {
    color: '#94A3B8',
    fontSize: 12,
    marginTop: 2,
    marginBottom: 16,
  },
  inputLabel: {
    color: '#CBD5E1',
    fontSize: 10,
    fontWeight: 'bold',
    marginBottom: 6,
    letterSpacing: 0.5,
  },
  reasonRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 12,
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
    backgroundColor: '#0038A8',
    borderColor: '#38BDF8',
  },
  reasonText: {
    color: '#94A3B8',
    fontSize: 11,
  },
  reasonTextActive: {
    color: '#FFFFFF',
    fontWeight: 'bold',
  },
  textInput: {
    backgroundColor: '#1E293B',
    borderRadius: 10,
    padding: 10,
    color: '#FFFFFF',
    fontSize: 13,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#334155',
  },
  modalButtonRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 8,
  },
  cancelModalBtn: {
    flex: 1,
    backgroundColor: '#1E293B',
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
  },
  cancelBtnText: {
    color: '#94A3B8',
    fontSize: 13,
    fontWeight: 'bold',
  },
  submitModalBtn: {
    flex: 1,
    backgroundColor: '#FCD116',
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
  },
  submitBtnText: {
    color: '#0B192C',
    fontSize: 13,
    fontWeight: 'bold',
  },
  alertHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 14,
  },
  alertDetailBox: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    alignItems: 'center',
  },
  alertStudentName: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '900',
    marginBottom: 6,
  },
  alertBadge: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 6,
    marginBottom: 8,
  },
  alertBadgeText: {
    fontSize: 11,
    fontWeight: '900',
  },
  alertTimestamp: {
    color: '#CBD5E1',
    fontSize: 13,
    fontWeight: '600',
  },
  alertDevice: {
    color: '#94A3B8',
    fontSize: 11,
    marginTop: 2,
  },
  dismissBtn: {
    backgroundColor: '#FCD116',
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
  },
  dismissBtnText: {
    color: '#0B192C',
    fontSize: 13,
    fontWeight: 'bold',
  }
});
