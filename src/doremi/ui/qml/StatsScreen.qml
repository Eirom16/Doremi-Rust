import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    property var screenVm: null

    // themeBridge (ThemeBridge) y vm (StatsViewModel) llegan por contexto.
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"
    readonly property color accentColor: root.colors["accent"]

    function accentWithAlpha(a) {
        return Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, a)
    }

    function playsText(n) {
        return n > 1 ? n + " veces" : "1 vez"
    }

    Rectangle {
        anchors.fill: parent
        color: root.colors["bg_base"]
    }

    Flickable {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingLg
        anchors.rightMargin: Theme.spacingLg
        anchors.topMargin: Theme.spacingMd
        anchors.bottomMargin: themeBridge.miniPlayerVisible ? 112 : Theme.spacingLg
        contentWidth: width
        contentHeight: contentCol.height
        clip: true
        flickableDirection: Flickable.VerticalFlick

        ColumnLayout {
            id: contentCol
            width: parent.width
            spacing: Theme.spacingLg

            // ── Header ────────────────────────────────────────────────
            ColumnLayout {
                spacing: Theme.spacingXxs
                Label {
                    text: "Tus Estadísticas"
                    color: root.colors["text_primary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeDisplay * 0.75
                    font.weight: Font.Bold
                }
                Label {
                    text: "Analiza tus hábitos musicales y descubre tus canciones favoritas"
                    color: root.colors["text_secondary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeBody
                }
            }

            // ── Período ───────────────────────────────────────────────
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingSm
                FilterSelect {
                    objectName: "statsPeriodFilter"
                    label: "Período"
                    selectedKey: screenVm.period
                    options: [{key:"today", label:"Hoy"}, {key:"week", label:"Semana"}, {key:"month", label:"Mes"}, {key:"year", label:"Año"}, {key:"all", label:"Todo"}]
                    onChoiceSelected: function(key) { screenVm.select_period(key) }
                }
                Item { Layout.fillWidth: true }
            }

            RowLayout {
                Layout.fillWidth: true
                Label { text: "Doremi Wrapped"; color: root.colors["text_primary"]; font.pixelSize: Theme.typeHeading }
                HeaderButton {
                    id: wrappedButton
                    objectName: "wrappedMenuButton"
                    text: "Generar resumen ▾"
                    accessibleName: "Generar resumen Doremi Wrapped"
                    onClicked: wrappedMenu.open()
                    ContextMenu {
                        id: wrappedMenu
                        objectName: "wrappedPeriodMenu"
                        y: wrappedButton.height
                        ContextMenuItem { objectName: "wrappedMonthAction"; text: "Este mes"; onTriggered: screenVm.request_wrapped("month") }
                        ContextMenuItem { objectName: "wrappedYearAction"; text: "Este año"; onTriggered: screenVm.request_wrapped("year") }
                    }
                }
                Item { Layout.fillWidth: true }
            }
            Rectangle {
                visible: screenVm.wrapped.title !== undefined && screenVm.wrapped.plays > 0
                Layout.fillWidth: true
                Layout.preferredHeight: 160
                radius: Theme.radiusLg
                color: root.colors["bg_surface"]
                border.width: 1
                border.color: root.colors["border"]
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMd
                    Label { text: screenVm.wrapped.title || ""; color: root.colors["accent"]; font.pixelSize: Theme.typeHeading }
                    Label { text: (screenVm.wrapped.minutes || 0) + " minutos de música"; color: root.colors["text_primary"] }
                    Label { visible: !!screenVm.wrapped.top_artist; text: "Artista favorito · " + screenVm.wrapped.top_artist; color: root.colors["text_secondary"] }
                    Label { visible: !!screenVm.wrapped.top_song; text: "Canción favorita · " + screenVm.wrapped.top_song; color: root.colors["text_secondary"] }
                    Label { text: (screenVm.wrapped.discoveries || 0) + " descubrimientos"; color: root.colors["text_secondary"] }
                }
            }

            Label {
                visible: !screenVm.loading && screenVm.totalPlays > 0
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: root.colors["text_secondary"]
                text: (screenVm.insights.unique_songs || 0) + " canciones únicas · "
                    + (screenVm.insights.discoveries || 0) + " descubiertas"
                    + (screenVm.insights.completion_rate != null ? " · Escucha media: " + Math.round(screenVm.insights.completion_rate * 100) + "%" : "")
                    + (screenVm.insights.skip_rate != null ? " · Saltos: " + Math.round(screenVm.insights.skip_rate * 100) + "%" : "")
            }

            Repeater {
                model: !screenVm.loading ? (screenVm.insights.top_artists || []) : []
                Label {
                    required property var modelData
                    text: modelData.title + " · " + modelData.plays + " reproducciones"
                    color: root.colors["text_primary"]
                    font.family: Theme.fontFamily
                }
            }
            Label {
                visible: !screenVm.loading && !!screenVm.insights.peak_hour && !!screenVm.insights.peak_hour.hour
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: root.colors["text_secondary"]
                text: "Más reproducciones a las " + (screenVm.insights.peak_hour ? screenVm.insights.peak_hour.hour : "")
                    + ":00 · Día más activo: " + (screenVm.insights.active_day ? screenVm.insights.active_day.day || "" : "")
            }
            Repeater {
                model: !screenVm.loading ? (screenVm.insights.top_collections || []) : []
                Label {
                    required property var modelData
                    text: (modelData.type === "album" ? "Álbum · " : "Playlist · ") + modelData.title + " · " + modelData.plays
                    color: root.colors["text_secondary"]
                    font.family: Theme.fontFamily
                }
            }

            ColumnLayout {
                visible: screenVm.loading
                Layout.fillWidth: true
                spacing: Theme.spacingMd
                Item { Layout.preferredHeight: 80 }
                BusyIndicator {
                    Layout.alignment: Qt.AlignHCenter
                    running: screenVm.loading
                }
            }

            ColumnLayout {
                visible: !screenVm.loading && screenVm.errorText !== ""
                Layout.fillWidth: true
                spacing: Theme.spacingSm
                Item { Layout.preferredHeight: 80 }
                Label {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 440
                    text: screenVm.errorText
                    color: root.colors["error"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeBody
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }
                Button {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Reintentar"
                    Accessible.name: "Reintentar cargar estadísticas"
                    onClicked: screenVm.retry()
                }
            }

            // ── Cards ─────────────────────────────────────────────────
            RowLayout {
                visible: !screenVm.loading && screenVm.errorText === ""
                Layout.fillWidth: true
                spacing: Theme.spacingMd

                Repeater {
                    model: [
                        { "icon": "schedule", "value": screenVm.timeListened, "label": "Tiempo Escuchado" },
                        { "icon": "play_arrow", "value": "" + screenVm.totalPlays, "label": "Total Reproducidas" },
                        { "icon": "artist", "value": "" + screenVm.uniqueArtists, "label": "Artistas Únicos" }
                    ]

                    delegate: Rectangle {
                        id: statCard
                        required property var modelData

                        Layout.fillWidth: true
                        Layout.preferredHeight: 84
                        radius: Theme.radiusLg
                        color: root.colors["bg_elevated"]
                        border.width: 1
                        border.color: root.colors["border"]
                        HoverHandler { id: metricHover }
                        ToolTip.visible: modelData.icon === "artist" && metricHover.hovered
                        ToolTip.text: "Cuenta los créditos de artista guardados; las colaboraciones no se separan en artistas individuales."

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacingMd
                            spacing: Theme.spacingMd

                            Rectangle {
                                Layout.preferredWidth: 48
                                Layout.preferredHeight: 48
                                radius: 24
                                color: root.accentWithAlpha(0.15)

                                Text {
                                    anchors.centerIn: parent
                                    text: {
                                        if (statCard.modelData.icon === "schedule") return ""
                                        if (statCard.modelData.icon === "play_arrow") return ""
                                        if (statCard.modelData.icon === "artist") return ""
                                        return ""
                                    }
                                    font.family: root.iconFont
                                    font.pixelSize: 22
                                    color: root.accentColor
                                }
                            }

                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Label {
                                    text: statCard.modelData.value
                                    color: root.colors["text_primary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 20
                                    font.weight: Font.Bold
                                }
                                Label {
                                    text: statCard.modelData.label
                                    color: root.colors["text_secondary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeLabel
                                    font.weight: Font.Medium
                                }
                            }
                        }
                    }
                }
            }

            // ── Columnas: top songs + chart ───────────────────────────
            RowLayout {
                visible: !screenVm.loading && screenVm.errorText === ""
                Layout.fillWidth: true
                spacing: Theme.spacingLg

                // Top 5 canciones
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    spacing: Theme.spacingSm

                    Label {
                        text: "Tus 5 Más Escuchadas"
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeTitle
                        font.weight: Font.Bold
                    }

                    Label {
                        visible: screenVm.topSongs.rowCount() === 0
                        text: "No hay suficientes reproducciones registradas."
                        color: root.colors["text_secondary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                        Layout.preferredWidth: 320
                        horizontalAlignment: Text.AlignHCenter
                        Layout.topMargin: Theme.spacingLg
                    }

                    Repeater {
                        model: screenVm.topSongs

                        delegate: Rectangle {
                            id: songRow
                            required property int index
                            required property string title
                            required property string artist
                            required property int plays
                            required property string thumbnail

                            Layout.fillWidth: true
                            Layout.preferredHeight: 64
                            radius: Theme.radiusLg
                            color: songMa.containsMouse ? root.colors["bg_high"] : "transparent"
                            activeFocusOnTab: true
                            Accessible.role: Accessible.ListItem
                            Accessible.name: "Reproducir " + songRow.title + ", " + songRow.artist
                            Accessible.description: root.playsText(songRow.plays) + "; menú contextual disponible"
                            Keys.onReturnPressed: screenVm.play_at(songRow.index)
                            Keys.onSpacePressed: screenVm.play_at(songRow.index)
                            Keys.onPressed: (event) => {
                                if (event.key === Qt.Key_Enter) {
                                    screenVm.play_at(songRow.index)
                                    event.accepted = true
                                } else if (event.key === Qt.Key_Menu || (event.key === Qt.Key_F10 && (event.modifiers & Qt.ShiftModifier))) {
                                    songMenu.popup()
                                    event.accepted = true
                                }
                            }

                            MouseArea {
                                id: songMa
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                onClicked: (mouse) => {
                                    if (mouse.button === Qt.LeftButton)
                                        screenVm.play_at(songRow.index)
                                    else
                                        songMenu.popup()
                                }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: Theme.spacingSm
                                anchors.rightMargin: Theme.spacingSm
                                spacing: Theme.spacingMd

                                Rectangle {
                                    Layout.preferredWidth: 48
                                    Layout.preferredHeight: 48
                                    radius: Theme.radiusSm
                                    color: root.colors["bg_elevated"]
                                    clip: true

                                    Image {
                                        anchors.fill: parent
                                        source: songRow.thumbnail
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        cache: true
                                        visible: status === Image.Ready
                                    }
                                    Text {
                                        anchors.centerIn: parent
                                        visible: parent.children[0].status !== Image.Ready
                                        text: "" // music_note
                                        font.family: root.iconFont
                                        font.pixelSize: 20
                                        color: root.colors["text_secondary"]
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Label {
                                        text: songRow.title
                                        color: root.colors["text_primary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeBody
                                        font.weight: Font.Medium
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Label {
                                        text: songRow.artist + " — " + root.playsText(songRow.plays)
                                        color: root.colors["text_secondary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeLabel
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }

                                SongMenu {
                                    id: songMenu
                                    showLink: true
                                    property var track: ({})
                                    onAboutToShow: track = screenVm.topSongs.track_info(songRow.index)
                                    liked: !!track.is_liked
                                    downloaded: !!track.is_downloaded
                                    localTrack: (track.videoId || "").indexOf("local:") === 0
                                    hasArtist: !localTrack && !!track.artist
                                    onAction: function(name) { screenVm.song_action(songRow.index, name) }
                                }
                            }
                        }
                    }
                }

                // Gráfica semanal
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    spacing: Theme.spacingSm

                    Label {
                        text: "Actividad diaria" + (screenVm.insights.chart_days ? " · " + screenVm.insights.chart_days + " días" : "")
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeTitle
                        font.weight: Font.Bold
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 280
                        radius: Theme.radiusLg
                        color: root.colors["bg_elevated"]
                        border.width: 1
                        border.color: root.colors["border"]

                        Label {
                            visible: screenVm.chartMax === 0
                            anchors.centerIn: parent
                            text: "Sin datos suficientes para graficar"
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeBody
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spacingLg
                            anchors.bottomMargin: Theme.spacingLg + Theme.spacingMd
                            visible: screenVm.chartMax > 0
                            spacing: Theme.spacingSm

                            Repeater {
                                model: screenVm.chart

                                delegate: ColumnLayout {
                                    id: barCol
                                    required property string day
                                    required property int count

                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    spacing: 0

                                    // Valor encima
                                    Label {
                                        Layout.fillWidth: true
                                        text: barCol.count > 0 ? String(barCol.count) : ""
                                        color: root.colors["text_primary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeCaption
                                        font.weight: Font.Bold
                                        horizontalAlignment: Text.AlignHCenter
                                    }

                                    Item { Layout.fillHeight: true }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: {
                                            var avail = barCol.height - 40
                                            if (screenVm.chartMax <= 0) return 0
                                            return barCol.count > 0 ? Math.max(2, avail * barCol.count / screenVm.chartMax) : 0
                                        }
                                        radius: Theme.radiusSm
                                        color: root.accentColor
                                        opacity: barHover.hovered ? 1.0 : 0.75

                                        HoverHandler { id: barHover }
                                        ToolTip.visible: barHover.hovered
                                        ToolTip.text: barCol.day + " · " + barCol.count + " reproducciones"

                                        Behavior on Layout.preferredHeight {
                                            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
                                        }
                                    }
                                }
                            }
                        }

                        // Fila de etiquetas de día
                        RowLayout {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: Theme.spacingLg
                            anchors.topMargin: 0
                            spacing: Theme.spacingSm

                            Repeater {
                                model: screenVm.chart
                                delegate: Label {
                                    required property string day
                                    required property int index
                                    Layout.fillWidth: true
                                    text: screenVm.chart.rowCount() <= 10 || index % 5 === 0 || index === screenVm.chart.rowCount() - 1 ? day : ""
                                    color: root.colors["text_secondary"]
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.typeCaption
                                    horizontalAlignment: Text.AlignHCenter
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
