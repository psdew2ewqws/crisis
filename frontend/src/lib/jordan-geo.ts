// Jordan governorate GeoJSON + static facility data.
// GeoJSON coordinates are [longitude, latitude] as per GeoJSON spec.
// DB governorate values seen: 'amman','zarqa','irbid','karak','ajloun','عمان','معان','العقبة'

export interface Governorate {
  id: string
  name: string
  name_ar: string
  /** All values this governorate might appear as in the DB */
  dbKeys: string[]
  /** [lat, lng] map centre for panel positioning */
  center: [number, number]
  polygon: [number, number][][] // GeoJSON ring(s): [[lon,lat],...]
}

export const GOVERNORATES: Governorate[] = [
  {
    id: 'irbid',
    name: 'Irbid',
    name_ar: 'إربد',
    dbKeys: ['irbid', 'إربد'],
    center: [32.55, 35.85],
    polygon: [[[35.53, 33.37], [36.08, 33.37], [36.08, 32.70], [35.90, 32.55], [35.53, 32.55], [35.53, 33.37]]],
  },
  {
    id: 'mafraq',
    name: 'Mafraq',
    name_ar: 'المفرق',
    dbKeys: ['mafraq', 'المفرق'],
    center: [32.35, 37.20],
    polygon: [[[36.08, 33.37], [39.30, 33.37], [39.30, 31.83], [36.50, 31.83], [36.08, 32.70], [36.08, 33.37]]],
  },
  {
    id: 'ajloun',
    name: 'Ajloun',
    name_ar: 'عجلون',
    dbKeys: ['ajloun', 'عجلون'],
    center: [32.33, 35.75],
    polygon: [[[35.53, 32.55], [35.90, 32.55], [35.88, 32.22], [35.53, 32.22], [35.53, 32.55]]],
  },
  {
    id: 'jerash',
    name: 'Jerash',
    name_ar: 'جرش',
    dbKeys: ['jerash', 'جرش'],
    center: [32.28, 35.90],
    polygon: [[[35.90, 32.55], [36.08, 32.70], [36.22, 32.45], [36.08, 32.22], [35.88, 32.22], [35.90, 32.55]]],
  },
  {
    id: 'balqa',
    name: 'Balqa',
    name_ar: 'البلقاء',
    dbKeys: ['balqa', 'البلقاء'],
    center: [32.03, 35.73],
    polygon: [[[35.53, 32.22], [35.88, 32.22], [35.90, 31.88], [35.72, 31.70], [35.53, 31.75], [35.53, 32.22]]],
  },
  {
    id: 'amman',
    name: 'Amman',
    name_ar: 'عمان',
    dbKeys: ['amman', 'عمان'],
    center: [31.95, 35.93],
    polygon: [[[35.88, 32.22], [36.08, 32.22], [36.22, 32.45], [36.50, 31.83], [36.25, 31.65], [36.10, 31.65], [35.90, 31.88], [35.88, 32.22]]],
  },
  {
    id: 'zarqa',
    name: 'Zarqa',
    name_ar: 'الزرقاء',
    dbKeys: ['zarqa', 'الزرقاء'],
    center: [32.07, 36.09],
    polygon: [[[36.08, 32.70], [36.50, 31.83], [36.22, 32.45], [36.08, 32.70]]],
  },
  {
    id: 'madaba',
    name: 'Madaba',
    name_ar: 'مادبا',
    dbKeys: ['madaba', 'مادبا'],
    center: [31.72, 35.79],
    polygon: [[[35.53, 31.75], [35.72, 31.70], [35.90, 31.88], [36.10, 31.65], [35.90, 31.35], [35.68, 31.25], [35.53, 31.35], [35.53, 31.75]]],
  },
  {
    id: 'karak',
    name: 'Karak',
    name_ar: 'الكرك',
    dbKeys: ['karak', 'الكرك'],
    center: [31.18, 35.70],
    polygon: [[[35.53, 31.35], [35.68, 31.25], [35.90, 31.35], [36.10, 31.65], [36.50, 31.83], [36.50, 30.82], [35.50, 30.82], [35.53, 31.35]]],
  },
  {
    id: 'tafilah',
    name: 'Tafilah',
    name_ar: 'الطفيلة',
    dbKeys: ['tafilah', 'الطفيلة'],
    center: [30.84, 35.61],
    polygon: [[[35.50, 30.82], [36.50, 30.82], [36.50, 30.42], [35.48, 30.42], [35.50, 30.82]]],
  },
  {
    id: 'maan',
    name: "Ma'an",
    name_ar: 'معان',
    dbKeys: ['maan', "ma'an", 'معان'],
    center: [30.19, 35.73],
    polygon: [[[35.48, 30.42], [36.50, 30.42], [36.50, 31.83], [39.30, 31.83], [39.30, 29.18], [35.10, 29.18], [35.00, 29.55], [35.48, 30.42]]],
  },
  {
    id: 'aqaba',
    name: 'Aqaba',
    name_ar: 'العقبة',
    dbKeys: ['aqaba', 'العقبة'],
    center: [29.53, 35.00],
    polygon: [[[34.96, 29.60], [35.00, 29.55], [35.10, 29.18], [34.96, 29.18], [34.96, 29.60]]],
  },
]

export function matchGovernorate(dbValue: string | null): Governorate | undefined {
  if (!dbValue) return undefined
  const v = dbValue.trim().toLowerCase()
  return GOVERNORATES.find((g) => g.dbKeys.some((k) => k.toLowerCase() === v))
}

// ── Static facility data ──────────────────────────────────────────────────────

export interface Facility {
  name: string
  lat: number
  lng: number
}

export const CIVIL_DEFENSE: Record<string, Facility[]> = {
  amman: [
    { name: 'Civil Defense Directorate HQ', lat: 31.955, lng: 35.933 },
    { name: 'Sweileh Civil Defense', lat: 31.990, lng: 35.878 },
    { name: 'Sahab Civil Defense', lat: 31.870, lng: 36.012 },
  ],
  zarqa: [
    { name: 'Zarqa Civil Defense HQ', lat: 32.073, lng: 36.088 },
    { name: 'Russeifa Civil Defense', lat: 32.020, lng: 36.030 },
  ],
  irbid: [
    { name: 'Irbid Civil Defense Directorate', lat: 32.555, lng: 35.852 },
    { name: 'Ramtha Civil Defense', lat: 32.557, lng: 36.008 },
  ],
  balqa: [
    { name: 'As-Salt Civil Defense', lat: 32.033, lng: 35.728 },
    { name: 'Fuheis Civil Defense', lat: 31.993, lng: 35.840 },
  ],
  mafraq: [
    { name: 'Mafraq Civil Defense Directorate', lat: 32.342, lng: 36.200 },
    { name: 'Ruwayshid Civil Defense', lat: 32.503, lng: 38.196 },
  ],
  madaba: [{ name: 'Madaba Civil Defense', lat: 31.717, lng: 35.793 }],
  karak: [
    { name: 'Karak Civil Defense Directorate', lat: 31.185, lng: 35.704 },
    { name: 'Mu\'tah Civil Defense', lat: 31.039, lng: 35.716 },
  ],
  tafilah: [{ name: 'Tafilah Civil Defense', lat: 30.842, lng: 35.604 }],
  maan: [
    { name: "Ma'an Civil Defense Directorate", lat: 30.192, lng: 35.735 },
    { name: 'Wadi Rum Civil Defense', lat: 29.575, lng: 35.413 },
  ],
  aqaba: [
    { name: 'Aqaba Civil Defense Directorate', lat: 29.531, lng: 35.006 },
    { name: 'Aqaba Port Civil Defense', lat: 29.505, lng: 35.003 },
  ],
  ajloun: [{ name: 'Ajloun Civil Defense', lat: 32.333, lng: 35.752 }],
  jerash: [{ name: 'Jerash Civil Defense', lat: 32.282, lng: 35.900 }],
}

export const HOSPITALS: Record<string, Facility[]> = {
  amman: [
    { name: 'Al-Bashir Hospital', lat: 31.951, lng: 35.912 },
    { name: 'Jordan University Hospital', lat: 31.974, lng: 35.892 },
    { name: 'King Hussein Medical Center', lat: 31.980, lng: 35.930 },
    { name: 'Italian Hospital', lat: 31.960, lng: 35.925 },
  ],
  zarqa: [
    { name: 'Prince Hashem Military Hospital', lat: 32.065, lng: 36.098 },
    { name: 'Zarqa Governmental Hospital', lat: 32.071, lng: 36.083 },
  ],
  irbid: [
    { name: 'Princess Basma Hospital', lat: 32.548, lng: 35.848 },
    { name: 'Irbid Specialist Hospital', lat: 32.561, lng: 35.839 },
    { name: 'King Abdullah University Hospital', lat: 32.504, lng: 35.826 },
  ],
  balqa: [
    { name: 'Prince Ali Hospital (As-Salt)', lat: 32.036, lng: 35.735 },
    { name: 'Princess Rahma Hospital', lat: 32.030, lng: 35.722 },
  ],
  mafraq: [
    { name: 'Mafraq Governmental Hospital', lat: 32.345, lng: 36.198 },
    { name: 'Prince Hassan Hospital', lat: 32.350, lng: 36.205 },
  ],
  madaba: [{ name: 'Madaba Governmental Hospital', lat: 31.718, lng: 35.796 }],
  karak: [
    { name: 'Karak Governmental Hospital', lat: 31.183, lng: 35.700 },
    { name: 'Prince Hussein Hospital (Karak)', lat: 31.190, lng: 35.710 },
  ],
  tafilah: [{ name: 'Tafilah Governmental Hospital', lat: 30.840, lng: 35.601 }],
  maan: [
    { name: "Ma'an Governmental Hospital", lat: 30.190, lng: 35.732 },
    { name: 'Aqaba–Ma\'an Regional', lat: 30.195, lng: 35.736 },
  ],
  aqaba: [
    { name: 'Aqaba Governmental Hospital', lat: 29.528, lng: 35.003 },
    { name: 'Princess Haya Hospital', lat: 29.535, lng: 35.010 },
  ],
  ajloun: [{ name: 'Ajloun Governmental Hospital', lat: 32.330, lng: 35.748 }],
  jerash: [{ name: 'Jerash Governmental Hospital', lat: 32.279, lng: 35.897 }],
}
