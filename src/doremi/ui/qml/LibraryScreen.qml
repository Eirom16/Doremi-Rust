import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    property var screenVm: null

    // themeBridge (ThemeBridge) y vm (LibraryViewModel) llegan por contexto.
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"
    readonly property color accentColor: root.colors["accent"]

    function accentWithAlpha(a) {
        return Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, a)
    }

    readonly property var tabDefs: [
        { "key": "songs", "label": "Favoritas" },
        { "key": "albums", "label": "Álbumes" },
        { "key": "artists", "label": "Artistas" },
        { "key": "playlists", "label": "Playlists" }
    ]

    readonly property var emptyTexts: ({
        "songs": "No tienes canciones guardadas",
        "albums": "No tienes álbumes guardados",
        "artists": "No sigues a ningún artista",
        "playlists": "No tienes playlists"
    })

    function currentModel() {
        if (screenVm.tab === "songs") return screenVm.songs
        if (screenVm.tab === "albums") return screenVm.albums
        if (screenVm.tab === "artists") return screenVm.artists
        return screenVm.playlists
    }

    Rectangle {
        anchors.fill: parent
        color: root.colors["bg_base"]
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingLg
        anchors.rightMargin: Theme.spacingLg
        anchors.topMargin: Theme.spacingMd
        anchors.bottomMargin: themeBridge.miniPlayerVisible ? 112 : Theme.spacingLg
        spacing: Theme.spacingSm

        // ── Header ────────────────────────────────────────────────────
        Label {
            text: "Biblioteca"
            color: root.colors["text_primary"]
            font.family: Theme.fontFamily
            font.pixelSize: Theme.typeDisplay * 0.75
            font.weight: Font.DemiBold
            font.letterSpacing: -0.3
            Layout.fillWidth: true
        }

        // ── Tabs (pills) ──────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSm

            Repeater {
                model: root.tabDefs

                delegate: Rectangle {
                    id: tabPill
                    required property var modelData
                    readonly property bool active: screenVm.tab === modelData.key

                    Layout.preferredWidth: tabLabel.implicitWidth + Theme.spacingLg * 1.5
                    Layout.preferredHeight: 36
                    radius: Theme.radiusPill
                    color: active ? root.accentWithAlpha(0.15)
                                  : (tabMa.containsMouse ? root.colors["bg_elevated"] : "transparent")
                    border.width: 1
                    border.color: active ? root.accentWithAlpha(0.3) : "transparent"

                    Label {
                        id: tabLabel
                        anchors.centerIn: parent
                        text: tabPill.modelData.label
                        color: tabPill.active ? root.accentColor : root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    MouseArea {
                        id: tabMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: screenVm.set_tab(tabPill.modelData.key)
                    }
                }
            }

            Item { Layout.fillWidth: true }
        }

        // ── Filtro + orden ────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSm
            visible: !screenVm.authRequired

            TextField {
                id: filterField
                Layout.fillWidth: true
                Layout.preferredHeight: 36
                placeholderText: "Buscar en biblioteca"
                color: root.colors["text_primary"]
                placeholderTextColor: root.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: 13
                leftPadding: Theme.spacingSm
                rightPadding: Theme.spacingSm
                background: Rectangle {
                    radius: Theme.radiusSm
                    color: root.colors["bg_surface"]
                    border.width: 1
                    border.color: filterField.activeFocus ? root.accentColor : root.colors["border"]
                }
                onTextChanged: screenVm.set_filter(text)
            }

            ComboBox {
                id: sortCombo
                Layout.preferredHeight: 36
                Layout.preferredWidth: 150
                model: [
                    { "text": "Recientes", "value": "recent" },
                    { "text": "Título", "value": "title" },
                    { "text": "Artista", "value": "artist" }
                ]
                textRole: "text"
                valueRole: "value"
                onActivated: screenVm.set_sort(currentValue)

                contentItem: Label {
                    leftPadding: Theme.spacingSm
                    text: sortCombo.displayText
                    color: root.colors["text_primary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                background: Rectangle {
                    radius: Theme.radiusSm
                    color: root.colors["bg_surface"]
                    border.width: 1
                    border.color: sortCombo.hovered ? root.accentColor : root.colors["border"]
                }
                delegate: ItemDelegate {
                    id: sortDelegate
                    required property var modelData
                    width: sortCombo.width
                    contentItem: Label {
                        text: sortDelegate.modelData.text
                        color: root.colors["text_primary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: sortDelegate.hovered ? root.colors["bg_high"] : "transparent"
                    }
                }
                popup: Popup {
                    y: sortCombo.height
                    width: sortCombo.width
                    implicitHeight: contentItem.implicitHeight
                    padding: Theme.spacingXxs
                    contentItem: ListView {
                        clip: true
                        implicitHeight: contentHeight
                        model: sortCombo.popup.visible ? sortCombo.delegateModel : null
                        ScrollIndicator.vertical: ScrollIndicator {}
                    }
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: root.colors["bg_elevated"]
                        border.width: 1
                        border.color: root.colors["border"]
                    }
                }
            }
        }

        // ── Carga ─────────────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: screenVm.loading
            spacing: Theme.spacingMd
            Item { Layout.fillHeight: true }
            BusyIndicator {
                Layout.alignment: Qt.AlignHCenter
                running: screenVm.loading
            }
            Label {
                text: "Cargando biblioteca…"
                color: root.colors["text_secondary"]
                font.pixelSize: Theme.typeBody
                Layout.alignment: Qt.AlignHCenter
            }
            Item { Layout.fillHeight: true }
        }

        // ── Sin autenticación ─────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !screenVm.loading && screenVm.authRequired
            spacing: Theme.spacingMd
            Item { Layout.fillHeight: true }
            Label {
                text: "Inicia sesión para ver tu biblioteca"
                color: root.colors["text_primary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeTitle
                Layout.alignment: Qt.AlignHCenter
            }
            Item { Layout.fillHeight: true }
        }

        // ── Estado vacío ──────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !screenVm.loading && !screenVm.authRequired && root.currentModel().rowCount() === 0
            spacing: Theme.spacingMd
            Item { Layout.fillHeight: true }
            Label {
                text: root.emptyTexts[screenVm.tab] || ""
                color: root.colors["text_primary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeTitle
                font.weight: Font.DemiBold
                Layout.alignment: Qt.AlignHCenter
            }
            Label {
                visible: screenVm.tab === "songs"
                text: "Las canciones que marques como favoritas aparecerán aquí"
                color: root.colors["text_secondary"]
                font.pixelSize: Theme.typeBody
                Layout.alignment: Qt.AlignHCenter
            }
            Item { Layout.fillHeight: true }
        }

        // ── Canciones (lista) ─────────────────────────────────────────
        ListView {
            id: songsList
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !screenVm.loading && !screenVm.authRequired && screenVm.tab === "songs" && screenVm.songs.rowCount() > 0
            model: screenVm.songs
            clip: true
            spacing: Theme.spacingXxs
            cacheBuffer: 600

            delegate: Rectangle {
                id: songRow
                width: songsList.width
                height: 64
                radius: Theme.radiusLg
                color: songMa.containsMouse ? root.colors["bg_high"] : "transparent"

                required property int index
                required property string title
                required property string artist
                required property string duration
                required property string thumbnail
                required property string videoId

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
                            text: "" // library_music
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
                            text: songRow.artist
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    Label {
                        text: songRow.duration
                        color: root.colors["text_secondary"]
                        font.pixelSize: Theme.typeCaption
                        font.family: Theme.fontMono
                        visible: songRow.duration !== ""
                    }

                    ContextMenu {
                        id: songMenu
                        ContextMenuItem {
                            text: "Reproducir siguiente"
                            onTriggered: screenVm.song_action(songRow.index, "play_next")
                        }
                        ContextMenuItem {
                            text: "Añadir a la cola"
                            onTriggered: screenVm.song_action(songRow.index, "add_to_queue")
                        }
                        ContextMenuItem {
                            text: "Quitar de Favoritas"
                            onTriggered: screenVm.song_action(songRow.index, "like")
                        }
                        ContextMenuItem {
                            text: "Añadir a playlist"
                            onTriggered: screenVm.song_action(songRow.index, "add_to_playlist")
                        }
                        ContextMenuItem {
                            text: "Descargar"
                            onTriggered: screenVm.song_action(songRow.index, "download")
                        }
                        ContextMenuItem {
                            text: "Ir al artista"
                            onTriggered: screenVm.song_action(songRow.index, "go_artist")
                        }
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
            }

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
            }
        }

        // ── Grids (álbumes, artistas, playlists) ──────────────────────
        GridView {
            id: grid
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !screenVm.loading && !screenVm.authRequired && screenVm.tab !== "songs"
                     && root.currentModel().rowCount() > 0
            clip: true
            cacheBuffer: 400

            readonly property int cols: Math.max(2, Math.floor(width / 190))
            cellWidth: width / cols
            cellHeight: 220

            model: root.currentModel()

            delegate: Item {
                id: gridCell
                width: grid.cellWidth
                height: grid.cellHeight

                required property int index
                required property string thumbnail
                required property string navigate
                // cover fields según tab
                property string cardTitle: screenVm.tab === "artists"
                    ? (typeof name !== "undefined" ? name : "")
                    : (typeof title !== "undefined" ? title : "")
                property string cardSubtitle: screenVm.tab === "artists"
                    ? ""
                    : (screenVm.tab === "albums"
                        ? ((typeof artist !== "undefined" ? artist : "")
                           + (typeof year !== "undefined" && year !== "" ? " · " + year : ""))
                        : (typeof subtitle !== "undefined" ? subtitle : ""))
                property bool isDl: (typeof isDownloaded !== "undefined") ? isDownloaded : false

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingXs
                    radius: Theme.radiusLg
                    color: gridMa.containsMouse ? root.colors["bg_high"] : root.colors["bg_surface"]
                    border.width: 1
                    border.color: gridMa.containsMouse ? root.colors["border_focus"] : root.colors["border"]

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spacingSm
                        spacing: Theme.spacingXs

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: Theme.radiusMd
                            color: root.colors["bg_elevated"]
                            clip: true

                            Image {
                                anchors.fill: parent
                                source: gridCell.thumbnail
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                                visible: status === Image.Ready
                            }
                            Text {
                                anchors.centerIn: parent
                                visible: parent.children[0].status !== Image.Ready
                                text: screenVm.tab === "artists" ? "" : "" // person / library_music
                                font.family: root.iconFont
                                font.pixelSize: 36
                                color: root.colors["text_secondary"]
                            }

                            // Badge descargada
                            Rectangle {
                                visible: gridCell.isDl
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: Theme.spacingXs
                                width: dlBadge.implicitWidth + Theme.spacingSm
                                height: 22
                                radius: Theme.radiusPill
                                color: root.colors ? Qt.rgba(0, 0, 0, 0.7) : "#cc000000"

                                Row {
                                    anchors.centerIn: parent
                                    spacing: 2
                                    Text {
                                        text: "" // download_done
                                        font.family: root.iconFont
                                        font.pixelSize: 13
                                        color: root.colors["accent"]
                                    }
                                    Label {
                                        id: dlBadge
                                        text: "Descargada"
                                        color: root.colors["text_primary"]
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.typeCaption
                                    }
                                }
                            }
                        }

                        Label {
                            text: gridCell.cardTitle
                            color: root.colors["text_primary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                            font.weight: Font.Medium
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Label {
                            visible: gridCell.cardSubtitle !== ""
                            text: gridCell.cardSubtitle
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeCaption
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    MouseArea {
                        id: gridMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (gridCell.navigate)
                                screenVm.navigate(gridCell.navigate)
                        }
                    }
                }
            }

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
            }
        }
    }

    // ── FAB crear playlist ────────────────────────────────────────────
    Rectangle {
        id: fab
        visible: screenVm.tab === "playlists" && !screenVm.loading && !screenVm.authRequired
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: Theme.spacingLg
        anchors.bottomMargin: (themeBridge.miniPlayerVisible ? 112 : 0) + Theme.spacingMd
        width: 56
        height: 56
        radius: 28
        color: fabMa.containsMouse ? root.colors["accent_bright"] : root.accentColor

        Text {
            anchors.centerIn: parent
            text: "" // playlist_add
            font.family: root.iconFont
            font.pixelSize: 26
            color: root.colors["text_on_accent"]
        }
        MouseArea {
            id: fabMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: createDialog.open()
        }
    }

    // ── Diálogo crear playlist ────────────────────────────────────────
    Dialog {
        id: createDialog
        modal: true
        anchors.centerIn: Overlay.overlay
        width: 420
        padding: 0

        function resetAndFocus() {
            plTitle.text = ""
            plDesc.text = ""
            plTitle.forceActiveFocus()
        }
        onOpened: resetAndFocus()

        background: Rectangle {
            radius: Theme.radiusLg
            color: root.colors["bg_surface"]
            border.width: 1
            border.color: root.colors["border"]
        }

        header: Rectangle {
            height: 96
            radius: Theme.radiusLg
            color: root.accentWithAlpha(0.15)

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacingMd
                spacing: Theme.spacingXxs
                Text {
                    text: "" // playlist_add
                    font.family: root.iconFont
                    font.pixelSize: 30
                    color: root.accentColor
                }
                Label {
                    text: "Crear Nueva Playlist"
                    color: root.colors["text_primary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeTitle
                    font.weight: Font.DemiBold
                }
            }
        }

        contentItem: ColumnLayout {
            spacing: Theme.spacingSm

            TextField {
                id: plTitle
                Layout.fillWidth: true
                placeholderText: "Nombre de la playlist"
                color: root.colors["text_primary"]
                placeholderTextColor: root.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: 14
                leftPadding: Theme.spacingSm
                background: Rectangle {
                    radius: Theme.radiusSm
                    color: root.colors["bg_elevated"]
                    border.width: 1
                    border.color: plTitle.activeFocus ? root.accentColor : root.colors["border"]
                }
                onAccepted: createDialog.acceptIfValid()
            }
            TextField {
                id: plDesc
                Layout.fillWidth: true
                placeholderText: "Descripción (opcional)"
                color: root.colors["text_primary"]
                placeholderTextColor: root.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: 14
                leftPadding: Theme.spacingSm
                background: Rectangle {
                    radius: Theme.radiusSm
                    color: root.colors["bg_elevated"]
                    border.width: 1
                    border.color: plDesc.activeFocus ? root.accentColor : root.colors["border"]
                }
            }
        }

        footer: RowLayout {
            spacing: Theme.spacingSm

            Item { Layout.fillWidth: true }

            Rectangle {
                Layout.preferredWidth: cancelLbl.implicitWidth + Theme.spacingLg * 1.5
                Layout.preferredHeight: 40
                radius: Theme.radiusPill
                color: cancelMa.containsMouse ? root.colors["bg_high"] : root.colors["bg_elevated"]

                Label {
                    id: cancelLbl
                    anchors.centerIn: parent
                    text: "Cancelar"
                    color: root.colors["text_primary"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeLabel
                    font.weight: Font.DemiBold
                }
                MouseArea {
                    id: cancelMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: createDialog.close()
                }
            }

            Rectangle {
                Layout.preferredWidth: createLbl.implicitWidth + Theme.spacingLg * 1.5
                Layout.preferredHeight: 40
                radius: Theme.radiusPill
                color: createMa.containsMouse ? root.colors["accent_bright"] : root.accentColor

                Label {
                    id: createLbl
                    anchors.centerIn: parent
                    text: "Crear"
                    color: root.colors["text_on_accent"]
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.typeLabel
                    font.weight: Font.DemiBold
                }
                MouseArea {
                    id: createMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: createDialog.acceptIfValid()
                }
            }
        }

        function acceptIfValid() {
            if (plTitle.text.trim() !== "") {
                screenVm.create_playlist(plTitle.text, plDesc.text)
                createDialog.close()
            }
        }
    }
}
