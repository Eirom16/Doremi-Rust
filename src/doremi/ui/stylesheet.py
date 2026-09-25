DOREMI_QSS = """

/* ─── Dynamically mapped cards & buttons ───────────────────── */

/* SongCard, AlbumCard, ArtistCard, PlaylistCard texts */
QLabel[textRole="primary"] { color: #F1F0FF; background: transparent; }
QLabel[textRole="secondary"] { color: #9B9BC0; background: transparent; }

/* SongCard */
SongCard QLabel#thumbnail_placeholder { background: #1E1E38; color: #9B9BC0; border-radius: 8px; }
SongCard QLabel#thumbnail_image { background: transparent; border-radius: 8px; }
SongCard IconButton#btn_like[liked="false"] {
    background-color: transparent;
    color: #9B9BC0;
    border: none;
    border-radius: 20px;
}
SongCard IconButton#btn_like[liked="false"]:hover {
    background-color: rgba(244, 114, 182, 0.15);
    color: #F472B6;
}
SongCard IconButton#btn_like[liked="true"] {
    color: #F472B6;
    background: transparent;
    border: none;
    border-radius: 20px;
}
SongCard IconButton#btn_like[liked="true"]:hover {
    background-color: rgba(244, 114, 182, 0.15);
}
SongCard IconButton#btn_play {
    background-color: transparent;
    color: #F1F0FF;
    border: none;
    border-radius: 20px;
}
SongCard IconButton#btn_play:hover {
    background-color: rgba(167, 139, 250, 0.15);
    color: #A78BFA;
}
SongCard QPushButton#menu_btn {
    background: transparent;
    color: #9B9BC0;
    border: none;
    border-radius: 20px;
    font-family: 'Material Symbols Rounded';
    font-size: 26px;
}
SongCard QPushButton#menu_btn:hover {
    background-color: rgba(167, 139, 250, 0.15);
    color: #A78BFA;
}

/* AlbumCard, ArtistCard, PlaylistCard */
#albumCard, #artistCard, #playlistCard {
    background-color: #10101E;
    border-radius: 12px;
    border: 1px solid rgba(167,139,250,0.12);
}
#albumCard:hover, #artistCard:hover, #playlistCard:hover {
    background-color: #16162A;
    border-color: rgba(167,139,250,0.33);
}
#albumCard:focus, #artistCard:focus, #playlistCard:focus {
    border: 2px solid #A78BFA;
}

#albumCard QLabel#thumbnail_placeholder, #artistCard QLabel#thumbnail_placeholder, #playlistCard QLabel#thumbnail_placeholder {
    background: #1E1E38;
    color: #9B9BC0;
    border-radius: 12px;
}
#artistCard QLabel#thumbnail_placeholder { border-radius: 75px; }

/* Genre Buttons */
QPushButton[isGenreBtn="true"] {
    background: #16162A;
    color: #F1F0FF;
    border: 1px solid rgba(167,139,250,0.12);
    border-radius: 12px;
    font-size: 14px;
    font-weight: 700;
}
QPushButton[isGenreBtn="true"]:hover {
    background: #1E1E38;
    border-color: rgba(167,139,250,0.55);
}



/* ─── Global fonts ─────────────────────────────────────────── */
* {
    letter-spacing: 0px;
}

/* ─── Window and background ────────────────────────────────── */
QMainWindow, QDialog, QWidget#contentArea, QWidget#root {
    background-color: #0A0A14;
    color: #F1F0FF;
}

#screenStack, #settingsStack {
    background-color: #0A0A14;
}

QPushButton#primaryPlayBtn {
    background-color: #A78BFA;
    color: #0A0A14;
    border: none;
}
QPushButton#primaryPlayBtn:hover {
    background-color: #BBA4FC;
}
QPushButton#primaryPlayBtn:pressed {
    background-color: #8B5CF6;
}

/* ─── Accessibility Focus Rings ────────────────────────────── */
QPushButton:focus, QLineEdit:focus, QSlider:focus {
    outline: none;
    border: 2px solid #A78BFA;
    border-radius: 4px;
}
QPushButton#primaryPlayBtn:focus {
    border: 2px solid #F1F0FF;
}
QWidget#songCard:focus, QWidget#albumCard:focus, QWidget#artistCard:focus, QWidget#playlistCard:focus {
    border: 2px solid #A78BFA;
}

/* ─── Sidebar ──────────────────────────────────────────────── */
#navSidebar {
    background-color: #10101E;
    border-right: 1px solid rgba(167,139,250,0.07);
    min-width: 220px;
    max-width: 220px;
}

#navSidebar[collapsed="true"] {
    min-width: 64px;
    max-width: 64px;
}

/* ─── Mini Player ──────────────────────────────────────────── */
#miniPlayer {
    background-color: transparent;
}

/* ─── Status Bar ───────────────────────────────────────────── */
#appStatusBar, QStatusBar {
    background: #0A0A14;
    color: #6B6B9B;
    border: none;
    font-size: 11px;
    font-family: 'Inter';
}

QStatusBar::item {
    border: none;
}

/* ─── Scroll Areas ─────────────────────────────────────────── */
QScrollArea {
    background: transparent;
    border: none;
}

/* ─── Scroll Bars ──────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 8px 3px 8px 0;
}

QScrollBar::handle:vertical {
    background: rgba(255,255,255,0.12);
    border-radius: 3px;
    min-height: 36px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(167,139,250,0.42);
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    margin: 0 8px 3px 8px;
}

QScrollBar::handle:horizontal {
    background: rgba(255,255,255,0.12);
    border-radius: 3px;
    min-width: 36px;
}

QScrollBar::handle:horizontal:hover {
    background: rgba(167,139,250,0.42);
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    width: 0px;
    background: transparent;
}

/* ─── Line Edits (Inputs) ──────────────────────────────────── */
QLineEdit {
    background: #16162A;
    color: #F1F0FF;
    border: 1px solid rgba(167,139,250,0.15);
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 14px;
    selection-background-color: rgba(167,139,250,0.30);
}

QLineEdit:focus {
    border-color: #A78BFA;
    background: #1A1A30;
}

QLineEdit::placeholder {
    color: #4A4A6A;
}

/* ─── Combo Box ────────────────────────────────────────────── */
QComboBox {
    background: #1E1E38;
    color: #F1F0FF;
    border: 1px solid rgba(167,139,250,0.20);
    border-radius: 10px;
    padding: 7px 14px;
    font-size: 13px;
    min-width: 140px;
}

QComboBox:hover {
    border-color: rgba(167,139,250,0.42);
}

QComboBox:focus {
    border-color: #A78BFA;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background: #1E1E38;
    color: #F1F0FF;
    selection-background-color: rgba(167,139,250,0.20);
    border: 1px solid rgba(167,139,250,0.15);
    border-radius: 10px;
    padding: 4px;
}

/* ─── Sliders ──────────────────────────────────────────────── */
QSlider::groove:horizontal {
    background: #2A2A4A;
    height: 4px;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #A78BFA);
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #FFFFFF;
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
    border: 2px solid #A78BFA;
}

QSlider::handle:horizontal:hover {
    background: #A78BFA;
    border-color: #FFFFFF;
}

QSlider::groove:vertical {
    background: #2A2A4A;
    width: 4px;
    border-radius: 2px;
}

QSlider::sub-page:vertical {
    background: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #8B5CF6, stop:1 #A78BFA);
    border-radius: 2px;
}

QSlider::add-page:vertical {
    background: #2A2A4A;
    border-radius: 2px;
}

QSlider::handle:vertical {
    background: #FFFFFF;
    width: 16px;
    height: 16px;
    border-radius: 8px;
    margin: 0 -6px;
    border: 2px solid #A78BFA;
}

QSlider::handle:vertical:hover {
    background: #A78BFA;
    border-color: #FFFFFF;
}

/* ─── Tabs ─────────────────────────────────────────────────── */
QTabWidget::pane {
    border: none;
    background: transparent;
}

QTabBar::tab {
    background: transparent;
    color: #6B6B9B;
    padding: 10px 20px;
    border: none;
    font-family: 'Inter';
    font-size: 13px;
    font-weight: 700;
}

QTabBar::tab:selected {
    color: #A78BFA;
    border-bottom: 2px solid #A78BFA;
}

QTabBar::tab:hover {
    color: #F1F0FF;
}

/* ─── Context Menus ────────────────────────────────────────── */
QMenu {
    background: #1E1E38;
    color: #F1F0FF;
    border: 1px solid rgba(167,139,250,0.15);
    border-radius: 14px;
    padding: 6px;
    font-size: 13px;
}

QMenu::item {
    padding: 8px 20px;
    border-radius: 10px;
}

QMenu::item:selected {
    background: rgba(167,139,250,0.15);
    color: #A78BFA;
}

QMenu::separator {
    height: 1px;
    background: rgba(167,139,250,0.08);
    margin: 4px 8px;
}

/* ─── Tooltips ─────────────────────────────────────────────── */
QToolTip {
    background: #1E1E38;
    color: #F1F0FF;
    border: 1px solid rgba(167,139,250,0.20);
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
}

/* ─── Section Headers ──────────────────────────────────────── */
QLabel.sectionHeader {
    font-family: 'Inter';
    font-size: 20px;
    font-weight: 800;
    color: #F1F0FF;
    padding: 16px 0 8px 0;
}

QLabel#libraryHeader {
    color: #F1F0FF;
    background: transparent;
    font-family: 'Inter';
    font-weight: 800;
}

QLabel#libraryEmptyMessage {
    color: #9B9BC0;
    font-family: 'Inter';
    background: transparent;
}

/* ─── Cards ────────────────────────────────────────────────── */
.MusicCard, .AlbumCard {
    background-color: #16162A;
    border-radius: 14px;
    border: 1px solid rgba(167,139,250,0.08);
}

.MusicCard:hover, .AlbumCard:hover {
    background-color: #1E1E38;
    border-color: rgba(167,139,250,0.22);
}

#songCard {
    background-color: transparent;
    border-radius: 12px;
    padding: 6px;
}

#songCard:hover {
    background-color: rgba(167,139,250,0.06);
}
#songCard:focus {
    background-color: rgba(167,139,250,0.08);
    border: 2px solid #A78BFA;
}

/* ─── Global rounded corners for QFrame ────────────────────── */
QFrame {
    border-radius: 12px;
}

/* Exclude separators (HLine/VLine) from the global radius rule */
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    border-radius: 1px;
}

QFrame#queueSeparator {
    border-radius: 1px;
    background: rgba(167,139,250,0.08);
    max-width: 1px;
}

/* ─── Download Cards ───────────────────────────────────────── */
#downloadCard {
    background-color: #16162A;
    border-radius: 14px;
    border: 1px solid rgba(167,139,250,0.06);
}

#downloadCard:hover {
    background-color: #1E1E38;
    border-color: rgba(167,139,250,0.18);
}

/* ─── Settings specific ───────────────────────────────────── */
#settingsSidebar {
    background-color: #10101E;
    border-right: 1px solid rgba(167,139,250,0.08);
}
QLabel#settingsTitle, QLabel#settingsPageTitle {
    color: #F1F0FF;
    padding: 0 8px 12px 8px;
}
QLabel#settingsPageTitle {
    padding: 0 0 10px 0;
}
QWidget#settingsRow {
    border-radius: 12px;
    background: transparent;
}
QWidget#settingsRow:hover {
    background-color: rgba(167,139,250,0.05);
}
QLabel#settingsRowTitle {
    color: #F1F0FF;
}
QLabel#settingsRowDesc, QLabel#settingsSectionHeader {
    color: #9B9BC0;
}
QLabel#settingsSectionHeader {
    padding: 16px 20px 8px 20px;
}
QFrame#settingsCard {
    background-color: #16162A;
    border-radius: 16px;
    border: 1px solid rgba(167,139,250,0.08);
}
QFrame#settingsSeparator {
    background-color: rgba(167,139,250,0.06);
    max-height: 1px;
}

/* ─── Now Playing Screen ───────────────────────────────────── */
#nowPlayingScreen, #nowPlayingLeftPanel, #nowPlayingRightPanel,
#lyricsContainer, #relatedContainer {
    background: transparent;
}
QLabel#nowPlayingTitle {
    color: #F1F0FF;
    background: transparent;
}
QLabel#nowPlayingArtist {
    color: #9B9BC0;
    background: transparent;
}
QLabel#nowPlayingTimeCurrent, QLabel#nowPlayingTimeTotal {
    color: #9B9BC0;
    background: transparent;
}
QLabel#nowPlayingArtwork {
    background-color: rgba(255,255,255,0.08);
    border-radius: 24px;
}
QTabWidget#nowPlayingTabs {
    background: transparent;
    border: none;
}
QTabWidget#nowPlayingTabs::pane {
    background: transparent;
    border: none;
}
QTabWidget#nowPlayingTabs QTabBar::tab {
    color: #9B9BC0;
    background: transparent;
}
QTabWidget#nowPlayingTabs QTabBar::tab:selected {
    color: #A78BFA;
    border-bottom: 2px solid #A78BFA;
}
/* ─── Mini Player Internal Containers ──────────────────────── */
#miniPlayerInfo, #miniPlayerProgress {
    background: transparent;
}

/* ─── Playlist / Artist Screens ────────────────────────────── */
QLabel#playlistCover, QLabel#artistCover {
    background-color: #1E1E38;
    border-radius: 8px;
}
QLabel#artistCover {
    border-radius: 100px;
}
QLabel#playlistType, QLabel#artistType {
    color: #A78BFA;
}
QLabel#playlistTitle, QLabel#artistTitle {
    color: #F1F0FF;
}
QLabel#playlistMeta, QLabel#artistMeta {
    color: #9B9BC0;
}
QLabel#artistSectionHeader, QLabel#artistSectionHeader_2 {
    color: #F1F0FF;
    padding: 16px 0 8px 0;
}
"""
