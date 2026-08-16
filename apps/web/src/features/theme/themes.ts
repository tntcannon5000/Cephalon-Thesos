export type ThemeId =
  | "murmur-labyrinth"
  | "origin-archive"
  | "corpus-relay"
  | "zariman-residuum"
  | "vallis-survey"
  | "deimos-twinlight"
  | "void-darkness"
  | "sentient-eclipse";
export type ThemeColorScheme = "light" | "dark";
export type ActivityMotion =
  | "sigil"
  | "orbit"
  | "signal"
  | "fracture"
  | "gust"
  | "breathe"
  | "articulate";
export type EdgeMotion =
  | "traverse"
  | "drift"
  | "pulse"
  | "shimmer"
  | "sweep"
  | "breathe"
  | "articulate";
export type SceneProfile =
  | "labyrinth"
  | "archive"
  | "relay"
  | "zariman"
  | "vallis"
  | "deimos"
  | "void"
  | "sentient";

export interface ThemePalette {
  background: string;
  surface: string;
  surfaceSolid: string;
  surfaceRaised: string;
  surfaceHover: string;
  sidebar: string;
  header: string;
  line: string;
  lineStrong: string;
  text: string;
  textSoft: string;
  muted: string;
  mutedDim: string;
  accent: string;
  assistant: string;
  accentDim: string;
  secondary: string;
  danger: string;
  userBubble: string;
  focusInset: string;
  selectionText: string;
  scrim: string;
  shadow: string;
}

export interface SceneTheme {
  background: number;
  fog: number;
  particlePrimary: number;
  particleSecondary: number;
  rails: number;
  particleCount: number;
  particleOpacity: number;
  particleSize: number;
  railCount: number;
  railOpacity: number;
  driftSpeed: number;
  railAmplitude: number;
  fogDensity: number;
  profile: SceneProfile;
}

export interface ThemeDefinition {
  id: ThemeId;
  name: string;
  description: string;
  colorScheme: ThemeColorScheme;
  palette: ThemePalette;
  scene: SceneTheme;
  motion: {
    activity: ActivityMotion;
    edge: EdgeMotion;
    edgeDuration: string;
  };
}

export const DEFAULT_THEME_ID: ThemeId = "murmur-labyrinth";

export const themes: ThemeDefinition[] = [
  {
    id: "murmur-labyrinth",
    name: "Murmur Labyrinth",
    description: "Orokin geometry fractured by the Indifference.",
    colorScheme: "dark",
    palette: {
      background: "#070706",
      surface: "rgba(17, 16, 14, 0.92)",
      surfaceSolid: "#11100e",
      surfaceRaised: "#1a1815",
      surfaceHover: "#211e19",
      sidebar: "rgba(9, 9, 8, 0.94)",
      header: "rgba(7, 7, 6, 0.9)",
      line: "rgba(207, 194, 164, 0.24)",
      lineStrong: "rgba(220, 205, 171, 0.5)",
      text: "#f1efe9",
      textSoft: "#dcd8ce",
      muted: "#98938a",
      mutedDim: "#6a675f",
      accent: "#d4af67",
      assistant: "#e6d8ad",
      accentDim: "#80683d",
      secondary: "#b66557",
      danger: "#df7f76",
      userBubble: "rgba(35, 32, 28, 0.76)",
      focusInset: "rgba(212, 175, 103, 0.14)",
      selectionText: "#120e08",
      scrim: "rgba(0, 0, 0, 0.66)",
      shadow: "rgba(0, 0, 0, 0.48)",
    },
    scene: {
      background: 0x070706,
      fog: 0x070706,
      particlePrimary: 0xd4af67,
      particleSecondary: 0xb66557,
      rails: 0xc6bdad,
      particleCount: 360,
      particleOpacity: 0.34,
      particleSize: 0.013,
      railCount: 8,
      railOpacity: 0.095,
      driftSpeed: 0.008,
      railAmplitude: 0.11,
      fogDensity: 0.055,
      profile: "labyrinth",
    },
    motion: { activity: "sigil", edge: "traverse", edgeDuration: "7.2s" },
  },
  {
    id: "origin-archive",
    name: "Origin Archive",
    description: "A quiet cyan relay for long research sessions.",
    colorScheme: "dark",
    palette: {
      background: "#070b0e",
      surface: "rgba(11, 17, 21, 0.92)",
      surfaceSolid: "#0b1115",
      surfaceRaised: "#10171c",
      surfaceHover: "#10191e",
      sidebar: "rgba(6, 10, 13, 0.94)",
      header: "rgba(7, 11, 14, 0.9)",
      line: "rgba(180, 197, 204, 0.28)",
      lineStrong: "rgba(192, 209, 214, 0.56)",
      text: "#eef3f4",
      textSoft: "#dfe6e8",
      muted: "#8d9aa0",
      mutedDim: "#5f6b70",
      accent: "#5de4ec",
      assistant: "#a2f2f4",
      accentDim: "#438e94",
      secondary: "#d9aa55",
      danger: "#e17f7f",
      userBubble: "rgba(19, 27, 32, 0.72)",
      focusInset: "rgba(93, 228, 236, 0.13)",
      selectionText: "#061013",
      scrim: "rgba(0, 0, 0, 0.66)",
      shadow: "rgba(0, 0, 0, 0.48)",
    },
    scene: {
      background: 0x070b0e,
      fog: 0x070b0e,
      particlePrimary: 0x61e7ef,
      particleSecondary: 0xb8c4ca,
      rails: 0xb8c4ca,
      particleCount: 320,
      particleOpacity: 0.32,
      particleSize: 0.012,
      railCount: 9,
      railOpacity: 0.08,
      driftSpeed: 0.006,
      railAmplitude: 0.08,
      fogDensity: 0.055,
      profile: "archive",
    },
    motion: { activity: "orbit", edge: "drift", edgeDuration: "9s" },
  },
  {
    id: "corpus-relay",
    name: "Corpus Relay",
    description: "Cool industrial panels with precise signal light.",
    colorScheme: "dark",
    palette: {
      background: "#05090c",
      surface: "rgba(8, 16, 21, 0.93)",
      surfaceSolid: "#081015",
      surfaceRaised: "#0d1920",
      surfaceHover: "#12232b",
      sidebar: "rgba(5, 11, 15, 0.95)",
      header: "rgba(5, 9, 12, 0.91)",
      line: "rgba(142, 177, 190, 0.28)",
      lineStrong: "rgba(160, 198, 211, 0.56)",
      text: "#edf4f6",
      textSoft: "#d2e1e6",
      muted: "#8299a2",
      mutedDim: "#536870",
      accent: "#68bddd",
      assistant: "#b8e8f1",
      accentDim: "#417b91",
      secondary: "#d6b45e",
      danger: "#e28178",
      userBubble: "rgba(17, 31, 39, 0.78)",
      focusInset: "rgba(104, 189, 221, 0.14)",
      selectionText: "#061116",
      scrim: "rgba(0, 0, 0, 0.66)",
      shadow: "rgba(0, 0, 0, 0.48)",
    },
    scene: {
      background: 0x05090c,
      fog: 0x05090c,
      particlePrimary: 0x68bddd,
      particleSecondary: 0xd6b45e,
      rails: 0x8eb1be,
      particleCount: 280,
      particleOpacity: 0.29,
      particleSize: 0.011,
      railCount: 10,
      railOpacity: 0.075,
      driftSpeed: 0.004,
      railAmplitude: 0.045,
      fogDensity: 0.055,
      profile: "relay",
    },
    motion: { activity: "signal", edge: "pulse", edgeDuration: "5.6s" },
  },
  {
    id: "zariman-residuum",
    name: "Zariman Residuum",
    description: "A weathered colony ship split by quiet Void light.",
    colorScheme: "light",
    palette: {
      background: "#e7e2d6",
      surface: "rgba(246, 243, 235, 0.9)",
      surfaceSolid: "#f4f0e7",
      surfaceRaised: "#fefcf7",
      surfaceHover: "#ebe6da",
      sidebar: "rgba(238, 234, 224, 0.95)",
      header: "rgba(231, 226, 214, 0.9)",
      line: "rgba(56, 72, 72, 0.2)",
      lineStrong: "rgba(60, 74, 73, 0.42)",
      text: "#1b2427",
      textSoft: "#344144",
      muted: "#687174",
      mutedDim: "#879092",
      accent: "#91652e",
      assistant: "#235f65",
      accentDim: "#9b7d54",
      secondary: "#397a68",
      danger: "#9c3f3f",
      userBubble: "rgba(255, 253, 248, 0.82)",
      focusInset: "rgba(22, 125, 136, 0.12)",
      selectionText: "#fbf8f0",
      scrim: "rgba(36, 43, 43, 0.34)",
      shadow: "rgba(66, 57, 43, 0.2)",
    },
    scene: {
      background: 0xe7e2d6,
      fog: 0xe7e2d6,
      particlePrimary: 0x91652e,
      particleSecondary: 0x167d88,
      rails: 0x715b45,
      particleCount: 220,
      particleOpacity: 0.2,
      particleSize: 0.012,
      railCount: 7,
      railOpacity: 0.12,
      driftSpeed: 0.0028,
      railAmplitude: 0.035,
      fogDensity: 0.046,
      profile: "zariman",
    },
    motion: { activity: "fracture", edge: "shimmer", edgeDuration: "12s" },
  },
  {
    id: "vallis-survey",
    name: "Vallis Survey",
    description: "Cold telemetry moving across an open Venusian sky.",
    colorScheme: "light",
    palette: {
      background: "#e8f0f2",
      surface: "rgba(247, 250, 250, 0.91)",
      surfaceSolid: "#f7fafa",
      surfaceRaised: "#ffffff",
      surfaceHover: "#e1ebee",
      sidebar: "rgba(238, 244, 245, 0.96)",
      header: "rgba(232, 240, 242, 0.91)",
      line: "rgba(39, 77, 91, 0.2)",
      lineStrong: "rgba(49, 89, 104, 0.43)",
      text: "#15242b",
      textSoft: "#31444c",
      muted: "#60737b",
      mutedDim: "#899a9f",
      accent: "#1e6f95",
      assistant: "#176678",
      accentDim: "#6d98a8",
      secondary: "#b85d28",
      danger: "#a13d3d",
      userBubble: "rgba(255, 255, 255, 0.84)",
      focusInset: "rgba(0, 139, 154, 0.11)",
      selectionText: "#f7fbfc",
      scrim: "rgba(26, 45, 52, 0.32)",
      shadow: "rgba(39, 66, 75, 0.18)",
    },
    scene: {
      background: 0xe8f0f2,
      fog: 0xe8f0f2,
      particlePrimary: 0x315968,
      particleSecondary: 0xb85d28,
      rails: 0x1e6f95,
      particleCount: 190,
      particleOpacity: 0.19,
      particleSize: 0.01,
      railCount: 9,
      railOpacity: 0.115,
      driftSpeed: 0.0015,
      railAmplitude: 0.025,
      fogDensity: 0.044,
      profile: "vallis",
    },
    motion: { activity: "gust", edge: "sweep", edgeDuration: "8.4s" },
  },
  {
    id: "deimos-twinlight",
    name: "Deimos Twinlight",
    description: "Fass and Vome breathe across a living substrate.",
    colorScheme: "dark",
    palette: {
      background: "#120a13",
      surface: "rgba(28, 17, 26, 0.92)",
      surfaceSolid: "#1c111a",
      surfaceRaised: "#251720",
      surfaceHover: "#321d2b",
      sidebar: "rgba(16, 9, 16, 0.95)",
      header: "rgba(18, 10, 19, 0.91)",
      line: "rgba(200, 185, 158, 0.22)",
      lineStrong: "rgba(200, 185, 158, 0.46)",
      text: "#f2e8e4",
      textSoft: "#dfd1cf",
      muted: "#aa969b",
      mutedDim: "#725f67",
      accent: "#58d9d1",
      assistant: "#a7f1eb",
      accentDim: "#418e8b",
      secondary: "#e7663f",
      danger: "#f07c6f",
      userBubble: "rgba(48, 27, 42, 0.78)",
      focusInset: "rgba(88, 217, 209, 0.13)",
      selectionText: "#0f0a0e",
      scrim: "rgba(5, 1, 6, 0.72)",
      shadow: "rgba(0, 0, 0, 0.54)",
    },
    scene: {
      background: 0x120a13,
      fog: 0x120a13,
      particlePrimary: 0x58d9d1,
      particleSecondary: 0xe7663f,
      rails: 0xc8b99e,
      particleCount: 360,
      particleOpacity: 0.39,
      particleSize: 0.017,
      railCount: 6,
      railOpacity: 0.1,
      driftSpeed: 0.005,
      railAmplitude: 0.065,
      fogDensity: 0.06,
      profile: "deimos",
    },
    motion: { activity: "breathe", edge: "breathe", edgeDuration: "11s" },
  },
  {
    id: "void-darkness",
    name: "Void Darkness",
    description: "A lightless threshold traced in cold Void blue.",
    colorScheme: "dark",
    palette: {
      background: "#010207",
      surface: "rgba(4, 7, 16, 0.94)",
      surfaceSolid: "#040710",
      surfaceRaised: "#080d1a",
      surfaceHover: "#0c1426",
      sidebar: "rgba(1, 3, 9, 0.97)",
      header: "rgba(1, 2, 7, 0.95)",
      line: "rgba(103, 147, 221, 0.19)",
      lineStrong: "rgba(119, 164, 235, 0.42)",
      text: "#eef4ff",
      textSoft: "#d6e3f8",
      muted: "#8290aa",
      mutedDim: "#4b5770",
      accent: "#699cff",
      assistant: "#a9c8ff",
      accentDim: "#3d5f9e",
      secondary: "#7564d8",
      danger: "#e1788d",
      userBubble: "rgba(8, 14, 29, 0.82)",
      focusInset: "rgba(105, 156, 255, 0.13)",
      selectionText: "#02040a",
      scrim: "rgba(0, 1, 5, 0.8)",
      shadow: "rgba(0, 0, 0, 0.78)",
    },
    scene: {
      background: 0x010207,
      fog: 0x010207,
      particlePrimary: 0x699cff,
      particleSecondary: 0x7564d8,
      rails: 0x8cb7ff,
      particleCount: 210,
      particleOpacity: 0.31,
      particleSize: 0.011,
      railCount: 6,
      railOpacity: 0.075,
      driftSpeed: 0.0022,
      railAmplitude: 0.028,
      fogDensity: 0.074,
      profile: "void",
    },
    motion: { activity: "fracture", edge: "shimmer", edgeDuration: "10.8s" },
  },
  {
    id: "sentient-eclipse",
    name: "Sentient Eclipse",
    description: "Articulated signals awake in absolute black.",
    colorScheme: "dark",
    palette: {
      background: "#000000",
      surface: "rgba(4, 5, 6, 0.94)",
      surfaceSolid: "#040506",
      surfaceRaised: "#090a0b",
      surfaceHover: "#101214",
      sidebar: "rgba(0, 0, 0, 0.97)",
      header: "rgba(0, 0, 0, 0.96)",
      line: "rgba(184, 180, 170, 0.16)",
      lineStrong: "rgba(184, 180, 170, 0.34)",
      text: "#f1f3f4",
      textSoft: "#d9dcde",
      muted: "#858a8f",
      mutedDim: "#51565b",
      accent: "#d73b42",
      assistant: "#70d4de",
      accentDim: "#773036",
      secondary: "#70d4de",
      danger: "#f05d63",
      userBubble: "rgba(4, 5, 6, 0.9)",
      focusInset: "rgba(215, 59, 66, 0.13)",
      selectionText: "#ffffff",
      scrim: "rgba(0, 0, 0, 0.82)",
      shadow: "rgba(0, 0, 0, 0.82)",
    },
    scene: {
      background: 0x000000,
      fog: 0x000000,
      particlePrimary: 0xd73b42,
      particleSecondary: 0x70d4de,
      rails: 0xb8b4aa,
      particleCount: 128,
      particleOpacity: 0.36,
      particleSize: 0.012,
      railCount: 5,
      railOpacity: 0.09,
      driftSpeed: 0.001,
      railAmplitude: 0.015,
      fogDensity: 0.07,
      profile: "sentient",
    },
    motion: { activity: "articulate", edge: "articulate", edgeDuration: "9.6s" },
  },
];

export function isThemeId(value: string | null): value is ThemeId {
  return themes.some((theme) => theme.id === value);
}
