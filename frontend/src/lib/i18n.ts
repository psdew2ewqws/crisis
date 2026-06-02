import { create } from 'zustand'

// ───────────────────────────────────────────────────────────────────────────
// AEGIS i18n — Arabic-first, with a one-click toggle to English.
//
// The app defaults to Arabic (RTL). Strings are keyed by their *English source*
// text, so call sites read naturally — `t('Run Analysis')` — and any key that
// is missing from the Arabic map simply falls back to the English key. Toggling
// the locale flips `<html lang>` + `<html dir>` so the whole layout mirrors.
// ───────────────────────────────────────────────────────────────────────────

export type Locale = 'ar' | 'en'

function apply(locale: Locale) {
  if (typeof document === 'undefined') return
  const el = document.documentElement
  el.lang = locale
  el.dir = locale === 'ar' ? 'rtl' : 'ltr'
  try {
    localStorage.setItem('aegis-locale', locale)
  } catch {
    /* ignore */
  }
}

const stored =
  typeof localStorage !== 'undefined' ? (localStorage.getItem('aegis-locale') as Locale | null) : null
const initial: Locale = stored ?? 'ar'

// Apply before first paint so there is no LTR→RTL flash.
apply(initial)

interface LocaleState {
  locale: Locale
  setLocale: (l: Locale) => void
  toggle: () => void
}

export const useLocaleStore = create<LocaleState>((set) => ({
  locale: initial,
  setLocale: (l) => {
    apply(l)
    set({ locale: l })
  },
  toggle: () =>
    set((s) => {
      const next: Locale = s.locale === 'ar' ? 'en' : 'ar'
      apply(next)
      return { locale: next }
    }),
}))

// ───────────────────────────────────────────────────────────────────────────
// Arabic dictionary — keyed by the English source string.
// Add entries here; missing keys gracefully fall back to English.
// ───────────────────────────────────────────────────────────────────────────
const AR: Record<string, string> = {
  // ── Brand / chrome ──
  'AEGIS': 'إيجيس',
  'CRISIS CONSOLE': 'منصّة الأزمات',
  'Crisis Console': 'منصّة الأزمات',
  'Run Analysis': 'تشغيل التحليل',
  'OPERATIONS': 'العمليّات',
  'CASE · SERVICE': 'الحالة · الخدمة',
  'Loading services…': 'جارٍ تحميل الخدمات…',
  'Settings': 'الإعدادات',
  'Get Help': 'المساعدة',
  'Commander': 'القائد',
  'Cmdr. Haddad': 'العقيد حدّاد',
  'All services': 'كل الخدمات',
  'all services': 'كل الخدمات',
  'Search signals, entities...': 'ابحث في الإشارات والكيانات…',
  'Notifications & help': 'التنبيهات والمساعدة',
  'Switch to light mode': 'التبديل إلى الوضع الفاتح',
  'Switch to dark mode': 'التبديل إلى الوضع الداكن',
  'Switch to English': 'التبديل إلى الإنجليزية',
  'Switch to Arabic': 'التبديل إلى العربية',

  // ── Navigation (Sidebar OPS) ──
  'Dashboard': 'لوحة القيادة',
  'Signals': 'الإشارات',
  'Incident Graph': 'مخطّط الحادثة',
  'Root Cause': 'السبب الجذري',
  'Solutions': 'الحلول',
  'Simulation': 'المحاكاة',
  'Decisions': 'القرارات',
  'Deep Analysis': 'التحليل العميق',
  'Expert Chat': 'محادثة الخبير',

  // ── Dashboard view ──
  'Live voc360': 'voc360 مباشر',
  'Deer Graph Analysis': 'تحليل ديير غراف',
  'RECOMMENDATION': 'التوصية',
  'Done': 'تم',
  'Close': 'إغلاق',
  'Running…': 'قيد التشغيل…',
  'Analysis failed to stream.': 'تعذّر بثّ التحليل.',

  // ── Run stages ──
  'Connect': 'الاتصال',
  'Connecting to voc360': 'الاتصال بـ voc360',
  'Ingest': 'الاستيعاب',
  'Pulling citizen signals': 'سحب إشارات المواطنين',
  'Graph': 'المخطّط',
  'Building dependency graph': 'بناء مخطّط الاعتماديات',
  'Ranking problem clusters': 'ترتيب محاور المشكلات',
  'Recommend': 'التوصية',
  'Drafting recommendation': 'صياغة التوصية',

  // ── KPI titles (live voc360 + fallbacks) ──
  'Citizen Signals': 'إشارات المواطنين',
  'High / Critical': 'عالية / حرجة',
  'Root-Cause Clusters': 'محاور الأسباب الجذريّة',
  'Services Affected': 'الخدمات المتأثّرة',
  'Active Cases': 'الحالات النشطة',
  'Avg. Resolution': 'متوسّط الحلّ',
  'National Risk': 'الخطر الوطني',
  'Apex Confidence': 'ثقة القمّة',
  'Projected Risk': 'الخطر المتوقّع',
  'Time to Mitigate': 'زمن التخفيف',
  // KPI badges / subs
  'severity': 'الشدّة',
  'distinct': 'مميّزة',
  'the_data rows': 'صفوف البيانات',
  'high + critical complaints': 'شكاوى عالية + حرجة',
  'active problem clusters': 'محاور المشكلات النشطة',
  'distinct service_id': 'معرّفات خدمة مميّزة',
  'Critical threshold exceeded': 'تم تجاوز الحدّ الحرج',
  'Loud symptoms demoted': 'خُفِّضت الأعراض الصاخبة',
  '74% reduction post-sim': 'انخفاض 74% بعد المحاكاة',
  '6 tankers to hospital': '6 صهاريج إلى المستشفى',
  'signals': 'إشارة',
  'critical': 'حرجة',
  'cases': 'حالات',
  'hrs': 'ساعة',
  'min': 'دقيقة',

  // ── DataTable ──
  'Incidents': 'الحوادث',
  'Customize': 'تخصيص',
  'Column customization — coming soon': 'تخصيص الأعمدة — قريباً',
  'Loading…': 'جارٍ التحميل…',
  'today': 'اليوم',
  '1d': 'يوم',
  '{n}d': '{n} يوم',
  'No signals for this selection.': 'لا توجد إشارات لهذا الاختيار.',
  'No active root-cause clusters.': 'لا توجد محاور أسباب جذريّة نشطة.',
  'No solutions available.': 'لا توجد حلول متاحة.',
  'Critical': 'حرجة',
  'Elevated': 'مرتفعة',
  'Nominal': 'طبيعيّة',
  'SERVICE': 'الخدمة',
  'OBSERVATION': 'الملاحظة',
  'SEVERITY': 'الشدّة',
  'SENTIMENT': 'المشاعر',
  'OBSERVED': 'وقت الرصد',
  'ROOT-CAUSE CLUSTER': 'محور السبب الجذري',
  'REPORTS': 'البلاغات',
  'CLUSTER': 'المحور',
  'COUNTERMEASURE': 'الإجراء المضادّ',
  'FEASIBILITY': 'الجدوى',

  // ── SignalVolume ──
  'Signal Volume': 'حجم الإشارات',
  'Citizen signals · voc360 · the_data': 'إشارات المواطنين · voc360 · the_data',
  '30 days': '٣٠ يوماً',
  '90 days': '٩٠ يوماً',
  'All': 'الكل',
  'Loading volume…': 'جارٍ تحميل الحجم…',
  'No signal volume for this selection.': 'لا يوجد حجم إشارات لهذا الاختيار.',

  // ── Onboarding ──
  'AEGIS Crisis Console': 'منصّة إيجيس للأزمات',

  // ── Settings drawer ──
  'APPEARANCE': 'المظهر',
  'Dark Mode': 'الوضع الداكن',
  'Light Mode': 'الوضع الفاتح',
  'Switch to light theme': 'التبديل إلى السمة الفاتحة',
  'Switch to dark theme': 'التبديل إلى السمة الداكنة',
  'NOTIFICATIONS': 'التنبيهات',
  'Push Notifications': 'الإشعارات الفوريّة',
  'Coming soon': 'قريباً',
  'SECURITY': 'الأمان',
  'API Keys': 'مفاتيح الواجهة البرمجيّة',
  'Manage integrations': 'إدارة التكاملات',
  'RBAC Policies': 'سياسات الصلاحيات',
  'Role-based access control': 'التحكّم بالوصول حسب الدور',
  'Language': 'اللغة',
  'العربية': 'العربية',
  'English': 'الإنجليزية',
  'Switch interface language': 'تبديل لغة الواجهة',

  // ── Help drawer ──
  'Help & Support': 'المساعدة والدعم',
  'KEYBOARD SHORTCUTS': 'اختصارات لوحة المفاتيح',
  'Toggle wizard mini-tracker': 'تبديل متتبّع المعالج المصغّر',
  'Command palette (future)': 'لوحة الأوامر (مستقبلاً)',
  'Open help': 'فتح المساعدة',
  'RESOURCES': 'المصادر',
  'Documentation': 'التوثيق',
  'AEGIS user guide & API reference': 'دليل مستخدم إيجيس ومرجع الواجهة البرمجيّة',
  'Contact Support': 'تواصل مع الدعم',
  'ABOUT': 'حول',
  'Version': 'الإصدار',
  'Build': 'البناء',
  'Environment': 'البيئة',
  'Production': 'الإنتاج',

  // ── ErrorBoundary ──
  'This view hit an error': 'واجهت هذه الشاشة خطأً',
  'The rest of the console is still running. You can retry this view.':
    'بقيّة المنصّة لا تزال تعمل. يمكنك إعادة محاولة هذه الشاشة.',
  'Retry': 'إعادة المحاولة',

  // ── LiveGraph ──
  'Live Crisis Graph': 'مخطّط الأزمة المباشر',
  'voc360 connected': 'متصل بـ voc360',
  'db offline': 'قاعدة البيانات غير متصلة',
  'services': 'خدمة',
  'root causes': 'سبب جذري',
  'Run Deer Graph Flow': 'تشغيل ديير غراف',
  'Running flow…': 'تشغيل التدفق…',
  'loading graph…': 'جارٍ تحميل المخطّط…',
  'DEER GRAPH FLOW': 'تدفق ديير غراف',
  'connect': 'الاتصال',
  'ingest': 'الاستيعاب',
  'graph': 'المخطّط',
  'rootcause': 'السبب الجذري',
  'recommend': 'التوصية',
  'SIMULATION · MESA': 'المحاكاة · ميسا',
  'simulate intervention': 'محاكاة التدخّل',
  'running': 'قيد التشغيل',
  'no action': 'بلا تدخّل',
  'intervention': 'التدخّل',
  'Negativity peaks at {pct}%, settles in {ticks} ticks · critical services → {crit} · engine {eng}':
    'السلبيّة تصل إلى {pct}%، تستقر خلال {ticks} دورة · الخدمات الحرجة → {crit} · المحرّك {eng}',
  'Run a Mesa agent-based simulation of how the root cause propagates across the service graph — with vs without intervention.':
    'شغّل محاكاة وكلاء Mesa لكيفية انتشار السبب الجذري عبر مخطّط الخدمة — مع التدخّل وبدونه.',
  'RANKED ROOT CAUSES · RIL': 'الأسباب الجذريّة المرتّبة · RIL',
  'No root causes yet': 'لا توجد أسباب جذريّة بعد',
  'loading…': 'جارٍ التحميل…',

  // ── SignalsPage ──
  'Voice-of-Customer signal layer · {table} · {total} records': 'طبقة إشارات صوت العميل · {table} · {total} سجلّ',
  'Refresh': 'تحديث',
  'Search signal text…': 'ابحث في نص الإشارة…',
  'All severity': 'كل الشدات',
  'All sources': 'كل المصادر',
  'SIGNAL': 'الإشارة',
  'SOURCE': 'المصدر',
  'Could not load signals': 'تعذّر تحميل الإشارات',
  'Loading voc360 signals…': 'جارٍ تحميل إشارات voc360…',
  'No signals match these filters': 'لا توجد إشارات مطابقة لهذه الفلاتر',
  'Try clearing a filter or the search term.': 'جرّب إلغاء أحد الفلاتر أو مصطلح البحث.',
  'No results': 'لا توجد نتائج',
  'Page {n} / {m}': 'صفحة {n} / {m}',
  'Previous page': 'الصفحة السابقة',
  'Next page': 'الصفحة التالية',

  // ── SolutionsPage ──
  'Valid-solution engine · cause → countermeasure → expected impact': 'محرّك الحلول الصالحة · السبب → الإجراء المضادّ → التأثير المتوقّع',
  'grounded': 'مؤصَّل',
  '{n} decision authorized': '{n} قرار مخوَّل',
  '{n} decisions authorized': '{n} قرارات مخوَّلة',
  'Computing valid solutions from voc360 root causes…': 'حوسبة الحلول الصالحة من الأسباب الجذريّة لـ voc360…',
  'No active root-cause clusters to resolve.': 'لا توجد محاور أسباب جذريّة نشطة لحلّها.',
  'high feasibility': 'جدوى عالية',
  'medium feasibility': 'جدوى متوسطة',
  'low feasibility': 'جدوى منخفضة',
  'Expected impact': 'التأثير المتوقّع',
  'Confidence': 'الثقة',
  'Decision authorized': 'القرار مخوَّل',
  'Authorize': 'إذن',
  'Authorizing…': 'جارٍ التخويل…',
  'Clear the National Aid Fund disbursement backlog': 'إزالة تراكمات صندوق المعونة الوطنية',
  'National Aid Fund': 'صندوق المعونة الوطني',
  'Stabilise the Takaful platform': 'استقرار منصّة تكافل',
  'Ministry of Social Development': 'وزارة التنمية الاجتماعية',
  'Restore BRT / public-transit reliability': 'استعادة موثوقيّة BRT / النقل العام',
  'Greater Amman Municipality — Transport': 'أمانة عمّان الكبرى — النقل',
  'Review urgent-service fee policy': 'مراجعة سياسة رسوم الخدمة العاجلة',
  'Service Delivery Authority': 'هيئة تسليم الخدمات',
  'Reduce passport-service wait times': 'تقليل أوقات انتظار خدمة الجوازات',
  'Passports & Civil Status Dept.': 'دائرة الجوازات والأحوال المدنية',
  'Close the citizen-response gap': 'سدّ فجوة الردّ على المواطنين',
  'Owning service contact centre': 'مركز اتصال الخدمة المالكة',
  'Investigate administrative-conduct reports': 'التحقيق في تقارير السلوك الإداري',
  'Integrity & Anti-Corruption Commission': 'هيئة النزاهة ومكافحة الفساد',
  'Prioritise roads & infrastructure fixes': 'تخصيص أولوية لإصلاح الطرق والبنية التحتية',
  'Ministry of Public Works': 'وزارة الأشغال العامة',
  'Targeted intervention for the dominant complaint cluster': 'تدخّل مستهدف للمحور الشاكي المهيمن',
  'Owning service agency': 'جهة الخدمة المالكة',
  'Stand up a surge processing cell to clear the aged disbursement queue': 'إنشاء خلية معالجة طارئة لإزالة طابور الصرف المتأخر',
  'Publish a per-applicant status tracker to cut repeat enquiries': 'نشر متتبّع حالة لكل متقدّم لتقليل الاستفسارات المتكررة',
  'Reconcile pending case files against eligibility records weekly': 'تسوية ملفات الحالات المعلّقة مقابل سجلات الأهلية أسبوعياً',
  'Add capacity / retries on the Takaful submission endpoint': 'إضافة سعة / إعادة محاولات على نقطة إرسال تكافل',
  'Surface clear error messaging for failed applications': 'عرض رسائل خطأ واضحة للطلبات الفاشلة',
  'Add an offline fallback channel during outages': 'إضافة قناة احتياطية خارجية أثناء الانقطاعات',
  'Re-time the BRT schedule against observed peak demand': 'إعادة توقيت جدول BRT مقابل ذروة الطلب الملاحظة',
  'Deploy reserve buses on the most-complained corridors': 'نشر حافلات احتياطية على الممرات الأكثر شكوى',
  'Publish live arrival data to reduce wait-time complaints': 'نشر بيانات الوصول المباشرة لتقليل شكاوى وقت الانتظار',
  'Audit expedited-service fees against published tariffs': 'تدقيق رسوم الخدمة العاجلة مقابل التعريفات المنشورة',
  'Disclose fee breakdown at point of payment': 'الإفصاح عن تفاصيل الرسوم عند نقطة الدفع',
  'Open a fast refund path for over-charges': 'فتح مسار استرداد سريع للرسوم الزائدة',
  'Open additional appointment slots at the busiest centres': 'فتح مواعيد إضافية في المراكز الأكثر ازدحاماً',
  'Shift routine renewals to the e-channel': 'تحويل التجديدات الروتينية إلى القناة الإلكترونية',
  'Add SMS status updates to cut counter follow-ups': 'إضافة تحديثات الحالة عبر الرسائل النصية لتقليل المتابعات',
  'Set and publish a first-response SLA for inbound complaints': 'تحديد ونشر اتفاقية مستوى خدمة الردّ الأول للشكاوى الواردة',
  'Auto-acknowledge every submission with a ticket reference': 'التأكيد التلقائي على كل تقديم مع رقم تذكرة',
  'Escalate any case unanswered past the SLA window': 'تصعيد أي حالة لم تُجب بعد نافذة اتفاقية مستوى الخدمة',
  'Triage flagged conduct reports for severity and recurrence': 'فرز تقارير السلوك المُعلَّمة حسب الشدة والتكرار',
  'Refer substantiated cases to the relevant oversight body': 'إحالة الحالات المثبتة إلى الجهة الرقابية المعنية',
  'Publish anonymised outcome statistics to restore trust': 'نشر إحصائيات النتائج المجهولة لاستعادة الثقة',
  'Rank reported defects by complaint density and severity': 'ترتيب العيوب المُبلَّغة حسب كثافة الشكاوى وشدتها',
  'Dispatch maintenance crews to top-ranked locations first': 'إرسال فرق الصيانة إلى المواقع الأعلى تصنيفاً أولاً',
  'Confirm closure with citizens who reported each defect': 'تأكيد الإغلاق مع المواطنين الذين أبلغوا عن كل عيب',
  'Route this cluster to the owning agency with an assigned owner': 'توجيه هذا المحور إلى الجهة المالكة مع مالك مُخصَّص',
  'Brief the service team on the recurring problem pattern': 'إحاطة فريق الخدمة بنمط المشكلة المتكررة',
  'Track whether complaint volume on this cluster falls after action': 'تتبّع ما إذا كان حجم الشكاوى على هذا المحور ينخفض بعد الإجراء',

  // ── SimulationPage ──
  'Agent-based sentiment propagation across the live voc360 graph · {bold} the root-cause fix': 'انتشار المشاعر المستند إلى الوكلاء عبر مخطّط voc360 المباشر · {bold} إصلاح السبب الجذري',
  'before vs after': 'قبل وبعد',
  'Reset': 'إعادة تعيين',
  'Re-run simulation': 'إعادة تشغيل المحاكاة',
  'Simulating…': 'جارٍ المحاكاة…',
  'Could not reach the simulation engine: {err}': 'تعذّر الوصول إلى محرّك المحاكاة: {err}',
  'Building case graph and propagating sentiment…': 'بناء مخطّط الحالة ونشر المشاعر…',
  'No simulation result yet.': 'لا توجد نتيجة محاكاة بعد.',
  'Intervention target': 'هدف التدخّل',
  'Top-ranked root-cause cluster (auto-targeted)': 'محور السبب الجذري الأعلى تصنيفاً (مستهدف تلقائياً)',
  '{n} member segments damped at the source node': '{n} شريحة عضو مُخمَّدة عند العقدة المصدر',
  'Dominant cluster damped at the source node': 'المحور المهيمن مُخمَّد عند العقدة المصدر',
  'engine: {name}': 'المحرّك: {name}',
  'mesa unavailable · deterministic fallback': 'ميسا غير متاح · محرّك احتياطي حتمي',
  'Δ Mean negativity': 'Δ متوسّط السلبية',
  '{before} → {after} at final step': '{before} → {after} في الخطوة الأخيرة',
  'Δ Critical nodes': 'Δ العقد الحرجة',
  '{before} → {after} nodes over threshold': '{before} → {after} عقدة فوق الحد',
  'Δ Peak negativity': 'Δ ذروة السلبية',
  'Reduction in worst-tick sentiment load': 'انخفاض الحمل المشاعري في أسوأ دورة',
  'Ticks to settle': 'دورات الاستقرار',
  'Steps until the fixed system stabilizes': 'خطوات حتى يستقر النظام المُصلَّح',
  'Run parameters': 'معاملات التشغيل',
  'Mean Negativity': 'متوسّط السلبية',
  'Average sentiment load across all seated nodes': 'متوسّط الحمل المشاعري عبر جميع العقد الموجودة',
  'Complaint Volume': 'حجم الشكاوى',
  'Aggregate weighted inflow across the graph': 'التدفق المرجّح الإجمالي عبر المخطّط',
  'Critical Nodes': 'العقد الحرجة',
  'Nodes with sentiment > 0.7 (critical threshold)': 'عقد ذات مشاعر > ٠٫٧ (الحد الحرج)',
  'Before': 'قبل',
  'After fix': 'بعد الإصلاح',
  'No series data': 'لا توجد بيانات سلسلة',
  'After-fix trajectory': 'مسار ما بعد الإصلاح',
  'All three variables normalized to [0,1] over the post-intervention run': 'جميع المتغيرات الثلاثة مُسوَّية إلى [٠،١] عبر تشغيل ما بعد التدخّل',

  // ── DecisionsPage ──
  'Operator decision log over voc360 root causes': 'سجلّ قرارات المشغّل على الأسباب الجذريّة لـ voc360',
  '{logged} logged · {authorized} authorized · {pending} awaiting gate': '{logged} مسجّل · {authorized} مخوَّل · {pending} بانتظار البوابة',
  'offline': 'غير متصل',
  'HUMAN AUTHORIZATION REQUIRED': 'مطلوب التخويل البشري',
  '{n} proposed decision cannot take effect until a named officer authorizes it.': 'لا يمكن تنفيذ القرار المُقترح ({n}) حتى يُخوّله ضابط مُسمّى.',
  '{n} proposed decisions cannot take effect until a named officer authorizes them.': 'لا يمكن تنفيذ القرارات المُقترحة ({n}) حتى يُخوّلها ضابط مُسمّى.',
  'Could not load decisions — {err}': 'تعذّر تحميل القرارات — {err}',
  'Loading decision log…': 'جارٍ تحميل سجلّ القرارات…',
  'No decisions have been logged yet. Decisions are created from the Root Cause and Solutions views, then cleared through the authorization gate here.':
    'لم تُسجَّل أي قرارات بعد. يتم إنشاء القرارات من شاشتي السبب الجذري والحلول، ثم إجازتها عبر بوابة التخويل هنا.',
  'DECISION LOG · {n}': 'سجلّ القرارات · {n}',
  'DECISION': 'القرار',
  'ROOT CAUSE': 'السبب الجذري',
  'STATUS': 'الحالة',
  'AUTHORIZED BY': 'مُخوَّل من',
  'LOGGED': 'مسجّل',
  'GATE': 'البوابة',
  'Open this cluster in the graph': 'افتح هذا المحور في المخطّط',
  'unauthorized': 'غير مُخوَّل',
  'AUTHORIZATION GATE': 'بوابة التخويل',
  'Root cause': 'السبب الجذري',
  'Rationale': 'المنطق',
  'An authorizing officer name is required to clear the gate.': 'اسم الضابط المُخوِّل مطلوب لإجازة البوابة.',
  'Authorizing officer name': 'اسم الضابط المُخوِّل',
  'Cancel': 'إلغاء',
  'Reject': 'رفض',
  'Submitting…': 'جارٍ الإرسال…',
  'Proposed': 'مُقترح',
  'Approved': 'مُعتمد',
  'Rejected': 'مرفوض',
  'In progress': 'قيد التنفيذ',
  'cleared': 'مُجاز',

  // ── RootCausePage ──
  'Root Cause Analysis': 'تحليل السبب الجذري',
  'Ranked RIL problem clusters from voc360': 'محاور مشكلات RIL المرتّبة من voc360',
  '{clusters} clusters · {reports} citizen reports': '{clusters} محاور · {reports} بلاغ مواطن',
  'Open graph': 'افتح المخطّط',
  'Ranking clusters…': 'جارٍ ترتيب المحاور…',
  'No root-cause clusters returned by voc360.': 'لم تُعِد voc360 أي محاور أسباب جذريّة.',
  'RANKED ROOT CAUSES · RIL CLUSTERS': 'الأسباب الجذريّة المرتّبة · محاور RIL',
  'Select a cluster to inspect its evidence and recommended countermeasure.': 'اختر محوراً لفحص أدلّته والإجراء المضادّ المُوصى به.',
  'CLUSTER · RANK #{rank}': 'المحور · ترتيب #{rank}',
  'SCORE': 'الدرجة',
  'EVIDENCE SEGMENTS': 'شرائح الأدلة',
  'No sample segments returned for this cluster.': 'لم تُعِد أي شرائح عينة لهذا المحور.',
  'VALID SOLUTION': 'حلّ صالح',
  'Owner': 'المالك',
  'Feasibility': 'الجدوى',
  'View this cluster in the graph': 'اعرض هذا المحور في المخطّط',

  // ── DeepAnalysisPage ──
  'analysis grounded · why-chain · forecast · validation on real voc360 data': 'تحليل مؤصَّل · سلسلة الأسباب · التوقّع · التحقّق على بيانات voc360 الحقيقية',
  '{n} root-cause clusters in scope': '{n} محاور أسباب جذريّة ضمن النطاق',
  'Could not load the entity universe — {err}': 'تعذّر تحميل عالم الكيانات — {err}',
  'ANALYSIS TARGET': 'هدف التحليل',
  'Service': 'الخدمة',
  'Root-cause cluster (RIL)': 'محور السبب الجذري (RIL)',
  'No clusters returned by voc360.': 'لم تُعِد voc360 أي محاور.',
  'SELECTED': 'المُختار',
  'Suggested questions': 'أسئلة مقترحة',
  'awaiting backend': 'بانتظار الخلفية',
  'Type your own question…': 'اكتب سؤالك بنفسك…',
  'Ask': 'اسأل',
  'Why-chain · root-cause graph': 'سلسلة الأسباب · مخطّط الأسباب الجذريّة',
  'Tracing the why-chain…': 'جارٍ تتبّع سلسلة الأسباب…',
  'No grounded why-chain for this target.': 'لا توجد سلسلة أسباب مؤصَّلة لهذا الهدف.',
  'Click a node in the why-chain graph to inspect its grounded evidence.': 'انقر عقدة في مخطّط سلسلة الأسباب لفحص أدلّتها المؤصَّلة.',
  'Validation': 'التحقّق',
  'PASS': 'نجح',
  'FAIL': 'فشل',
  'No validation axes returned.': 'لم تُعِد أي محاور تحقّق.',
  'Evidence': 'الأدلة',
  'REAL CITIZEN SEGMENTS': 'شرائح مواطنين حقيقية',
  'No sample segments at this node.': 'لا توجد شرائح عينة في هذه العقدة.',
  'Forecast': 'التوقّع',
  'signal volume': 'حجم الإشارات',
  'negative-sentiment share': 'حصّة المشاعر السلبية',
  'Volume': 'الحجم',
  'Sentiment': 'المشاعر',
  'Escalating': 'متصاعد',
  'Stable': 'مستقر',
  'No history available to forecast this target.': 'لا توجد بيانات تاريخية للتوقّع لهذا الهدف.',
  'ESCALATION WATCHLIST · NEXT 14 DAYS': 'قائمة المراقبة التصاعدية · ١٤ يوماً القادمة',
  'GROUNDED Q&A · ANSWERS COMPOSED FROM REAL voc360 FACTS': 'سؤال وجواب مؤصَّل · إجابات مُركَّبة من حقائق voc360 الحقيقية',
  'Ask anything — e.g. why is Sanad rising? which problem will escalate next?': 'اسأل أي شيء — مثلاً: لماذا يرتفع Sanad؟ أي مشكلة ستتصاعد تالياً؟',
  'UNGROUNDED': 'غير مؤصَّل',
  'GROUNDED': 'مؤصَّل',
  'CITATIONS': 'الاستشهادات',
  'FOLLOW-UP': 'متابعة',
  'Agent Debate': 'نقاش الوكلاء',
  'Stop': 'إيقاف',
  'Deep research · Agent debate': 'بحث عميق · نقاش الوكلاء',
  'LightMem memory': 'ذاكرة LightMem',
  'axes': 'محاور',
  'Expert panel': 'لجنة الخبراء',
  'confidence': 'الثقة',
  'verdict': 'الحكم',
  'agents are debating…': 'الوكلاء يتناقشون…',
  'Generating grounded questions…': 'جارٍ إنشاء أسئلة مؤصَّلة…',
  'No suggested questions for this target.': 'لا توجد أسئلة مقترحة لهذا الهدف.',

  // ── ExpertChatPage ──
  'Gemma · Domain intelligence with guardrails': 'جيما · ذكاء مجال مع حواجز أمان',
  'MODEL OFFLINE': 'النموذج غير متصل',
  'Gemma model offline. Start Ollama and run {cmd} to enable AI responses. Guardrails still save normally.':
    'نموذج جيما غير متصل. ابدأ Ollama وشغّل {cmd} لتفعيل إجابات الذكاء الاصطناعي. حواجز الأمان لا تزال تحفظ بشكل طبيعي.',
  'Ask a domain question': 'اطرح سؤال مجال',
  'Ask about root causes, signals, forecasts, or any voc360 insight. If the answer is wrong, correct it — your correction becomes a guardrail for future answers.':
    'اسأل عن الأسباب الجذريّة والإشارات والتوقعات أو أي رؤية من voc360. إذا كانت الإجابة خاطئة، صحّحها — تصحيحك يصبح حاجز أمان للإجابات المستقبلية.',
  'What are the top root-cause clusters right now?': 'ما هي أهم محاور الأسباب الجذريّة الآن؟',
  'Which service is forecast to escalate?': 'أي خدمة من المتوقّع أن تتصاعد؟',
  'Explain the why-chain for urgent service fees': 'اشرح سلسلة الأسباب لرسوم الخدمة العاجلة',
  'Thinking…': 'جارٍ التفكير…',
  'Ask a domain question… (Enter to send, Shift+Enter for newline)': 'اطرح سؤال مجال… (Enter للإرسال، Shift+Enter لسطر جديد)',
  'Mark wrong answers with "Correct this" to add guardrails · Guardrails are saved to {file}': 'علّم الإجابات الخاطئة بـ "صحّح هذا" لإضافة حواجز أمان · تُحفظ في {file}',
  'Guardrails': 'حواجز الأمان',
  'Saved Guardrails': 'حواجز الأمان المحفوظة',
  '{active} active / {total} total': '{active} نشط / {total} إجمالي',
  'No guardrails saved yet. Approve a correct answer or correct a wrong one to add guardrails.':
    'لم تُحفظ أي حواجز أمان بعد. اعتماد إجابة صحيحة أو تصحيح خاطئة لإضافة حواجز أمان.',
  'Disable': 'تعطيل',
  'Enable': 'تفعيل',
  'Delete': 'حذف',
  'ADD CORRECTION AS GUARDRAIL': 'إضافة التصحيح كحاجز أمان',
  'Question:': 'السؤال:',
  'Type the correct answer…': 'اكتب الإجابة الصحيحة…',
  'Topic tag (optional)': 'وسم الموضوع (اختياري)',
  'Save Guardrail': 'حفظ حاجز الأمان',
  'Approve as Guardrail': 'اعتمد كحاجز أمان',
  'Correct this': 'صحّح هذا',
  'Approved as guardrail': 'مُعتمد كحاجز أمان',
  'Correction saved': 'حُفظ التصحيح',
  'GUARDRAIL APPLIED': 'حاجز أمان مطبَّق',
  'GUARDRAILS APPLIED': 'حواجز أمان مطبَّقة',

  // ── ProofPanel ──
  'PROOF': 'الإثبات',
  'IN PLAIN TERMS': 'باختصار',
  'AGENT DEBATE': 'نقاش الوكلاء',
  'Run agent debate on this issue': 'شغّل نقاش الوكلاء على هذه القضية',
  'Re-run debate': 'إعادة النقاش',
  'Show technical details': 'عرض التفاصيل التقنية',
  'Hide technical details': 'إخفاء التفاصيل التقنية',
  'Why does the problem happen · causal chain': 'لماذا تحدث المشكلة · السلسلة السببية',
  'root cause': 'السبب الجذري',
  'Proof strength': 'قوة الإثبات',
  'Evidence · citizen testimonies': 'الأدلة · شهادات المواطنين',
  'Related cases · source records': 'الحالات ذات الصلة · سجلات المصدر',
  'Forecast · trend': 'التوقّع · الاتجاه',
  'back': 'رجوع',
  'close': 'إغلاق',
  'preparing proof…': 'جارٍ تجهيز الإثبات…',
  '30-day': '٣٠ يوماً',
  'NO DATA': 'لا توجد بيانات',
  'STAT': 'إحصائي',
  'GROUNDED FALLBACK': 'احتياطي مؤصَّل',
  'Answer approved as guardrail ✓': 'الإجابة مُعتمدة كحاجز أمان ✓',
  'Failed to save guardrail': 'تعذّر حفظ حاجز الأمان',
  'Guardrail saved ✓': 'حُفظ حاجز الأمان ✓',
  'Guardrail deleted': 'حُذف حاجز الأمان',
}

export function translate(locale: Locale, key: string, vars?: Record<string, string | number>): string {
  let out = locale === 'ar' ? AR[key] ?? key : key
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      out = out.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v))
    }
  }
  return out
}

export type Dir = 'rtl' | 'ltr'

export function useT() {
  const locale = useLocaleStore((s) => s.locale)
  const t = (key: string, vars?: Record<string, string | number>) => translate(locale, key, vars)
  return { t, locale, dir: (locale === 'ar' ? 'rtl' : 'ltr') as Dir }
}

// Register additional translations at runtime (used by page modules to keep
// their own strings co-located). Safe to call repeatedly.
export function registerAr(entries: Record<string, string>) {
  Object.assign(AR, entries)
}
