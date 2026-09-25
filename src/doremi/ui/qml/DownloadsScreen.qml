import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Doremi 1.0

Item {
    id: root

    property var screenVm: null

    // themeBridge (ThemeBridge) y vm (DownloadsViewModel) llegan por contexto.
    readonly property var colors: themeBridge.colors
    readonly property string iconFont: "Material Symbols Rounded"
    readonly property color accentColor: root.colors["accent"]

    function accentWithAlpha(a) {
        return Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, a)
    }

    readonly property var tabDefs: [
        { "key": "songs", "label": "Canciones" },
        { "key": "albums", "label": "Álbumes" },
        { "key": "playlists", "label": "Playlists Completas" }
    ]

    readonly property var statusDefs: [
        { "key": "all", "label": "Todas" },
        { "key": "completed", "label": "Completadas" },
        { "key": "active", "label": "En curso" },
        { "key": "error", "label": "Errores" }
    ]

    readonly property var emptyTexts: ({
        "songs": { "all": "No hay descargas aquí.", "completed": "No hay descargas completadas.",
                   "active": "No hay descargas en curso.", "error": "No hay descargas con error." },
        "albums": { "all": "No hay álbumes descargados." },
        "playlists": { "all": "No hay playlists descargadas." }
    })

    function emptyText() {
        var byTab = root.emptyTexts[screenVm.tab] || {}
        return byTab[screenVm.statusFilter] || byTab["all"] || ""
    }

    function statusLabel(status, progress, speed) {
        if (status === "completed") return ""
        if (status === "error") return "Error"
        if (status === "paused") return "Pausada"
        if (status === "downloading") return Math.round(progress) + "% • " + speed
        return "En cola"
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
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSm

            Label {
                text: "Descargas"
                color: root.colors["text_primary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeDisplay * 0.75
                font.weight: Font.DemiBold
                font.letterSpacing: -0.3
            }

            Item { Layout.fillWidth: true }

            // Toolbar de selección
            RowLayout {
                spacing: Theme.spacingSm
                visible: screenVm.selectionMode

                HeaderButton {
                    text: "Seleccionar Todo"
                    onClicked: screenVm.select_all()
                }
                HeaderButton {
                    text: "Borrar Seleccionados (" + screenVm.selectedCount + ")"
                    danger: true
                    visible: screenVm.selectedCount > 0
                    onClicked: confirmBatch.openFor(false)
                }
                HeaderButton {
                    text: "Borrar Todo"
                    danger: true
                    onClicked: confirmBatch.openFor(true)
                }
            }

            HeaderButton {
                text: screenVm.selectionMode ? "Cancelar" : "Seleccionar"
                active: screenVm.selectionMode
                onClicked: screenVm.toggle_selection_mode()
            }
        }

        // ── Tabs ──────────────────────────────────────────────────────
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
                        color: tabPill.active ? root.accentColor : root.colors["text_secondary"]
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

        // ── Filtros de estado (solo tab canciones) ────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingXs
            visible: screenVm.tab === "songs"

            Repeater {
                model: root.statusDefs
                delegate: Rectangle {
                    id: chip
                    required property var modelData
                    readonly property bool active: screenVm.statusFilter === modelData.key

                    Layout.preferredWidth: chipLabel.implicitWidth + Theme.spacingMd
                    Layout.preferredHeight: 30
                    radius: Theme.radiusPill
                    color: chipMa.containsMouse ? root.colors["bg_elevated"] : "transparent"
                    border.width: 1
                    border.color: active ? root.accentColor : root.colors["border"]

                    Label {
                        id: chipLabel
                        anchors.centerIn: parent
                        text: chip.modelData.label
                        color: chip.active ? root.accentColor : root.colors["text_secondary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeCaption
                        font.weight: Font.DemiBold
                    }
                    MouseArea {
                        id: chipMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: screenVm.set_status_filter(chip.modelData.key)
                    }
                }
            }

            Item { Layout.fillWidth: true }
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
            Item { Layout.fillHeight: true }
        }

        // ── Vacío ─────────────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !screenVm.loading
                     && ((screenVm.tab === "songs" && screenVm.songs.rowCount() === 0)
                         || (screenVm.tab !== "songs" && screenVm.groups.rowCount() === 0))
            spacing: Theme.spacingMd
            Item { Layout.fillHeight: true }
            Label {
                text: root.emptyText()
                color: root.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeTitle
                Layout.alignment: Qt.AlignHCenter
            }
            Item { Layout.fillHeight: true }
        }

        // ── Canciones ─────────────────────────────────────────────────
        ListView {
            id: songsList
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !screenVm.loading && screenVm.tab === "songs" && screenVm.songs.rowCount() > 0
            model: screenVm.songs
            clip: true
            spacing: Theme.spacingXs
            cacheBuffer: 600

            delegate: Rectangle {
                id: row
                width: songsList.width
                height: 64
                radius: Theme.radiusLg
                color: rowMa.containsMouse ? root.colors["bg_high"] : root.colors["bg_surface"]
                border.width: 1
                border.color: root.colors["border"]

                required property int index
                required property string videoId
                required property string title
                required property string artist
                required property string playlistTitle
                required property string thumbnail
                required property string status
                required property double progress
                required property string speed
                required property bool isLiked
                required property bool selected

                // Click de fila completa: seleccionar o reproducir.
                // Va ANTES del contenido para quedar DEBAJO de los botones
                // (el último hijo recibe los eventos en regiones solapadas).
                MouseArea {
                    id: rowMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (screenVm.selectionMode)
                            screenVm.toggle_item_selected(row.index)
                        else if (row.status === "completed")
                            screenVm.play_at(row.index)
                    }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spacingSm
                    anchors.rightMargin: Theme.spacingSm
                    spacing: Theme.spacingMd

                    // Checkbox (modo selección)
                    Rectangle {
                        visible: screenVm.selectionMode
                        Layout.preferredWidth: 20
                        Layout.preferredHeight: 20
                        radius: 10
                        color: row.selected ? root.accentColor : "transparent"
                        border.width: 2
                        border.color: row.selected ? root.accentColor : root.colors["border"]

                        Text {
                            anchors.centerIn: parent
                            visible: row.selected
                            text: "" // check
                            font.family: root.iconFont
                            font.pixelSize: 12
                            color: root.colors["text_on_accent"]
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: 48
                        Layout.preferredHeight: 48
                        radius: Theme.radiusSm
                        color: root.colors["bg_elevated"]
                        clip: true

                        Image {
                            anchors.fill: parent
                            source: row.thumbnail
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
                            font.pixelSize: 22
                            color: root.colors["text_secondary"]
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Label {
                            text: row.title
                            color: root.colors["text_primary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeBody
                            font.weight: Font.Medium
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Label {
                            text: row.playlistTitle
                                  ? row.artist + " • " + row.playlistTitle
                                  : row.artist
                            color: root.colors["text_secondary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        // Barra de progreso (descargas en curso)
                        Rectangle {
                            visible: row.status === "downloading" || row.status === "queued"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 4
                            radius: 2
                            color: root.colors["bg_high"]

                            Rectangle {
                                width: parent.width * Math.max(0, Math.min(100, row.progress)) / 100
                                height: parent.height
                                radius: 2
                                color: root.accentColor
                            }
                        }
                    }

                    // Estado
                    Label {
                        visible: text !== ""
                        text: root.statusLabel(row.status, row.progress, row.speed)
                        color: row.status === "error" ? root.colors["error"] : root.colors["text_secondary"]
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.typeLabel
                    }

                    // Like
                    Rectangle {
                        visible: !screenVm.selectionMode && row.status === "completed"
                        width: 36; height: 36; radius: 18
                        color: likeMa.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent"

                        Text {
                            anchors.centerIn: parent
                            text: "" // favorite
                            font.family: root.iconFont
                            font.pixelSize: 20
                            color: row.isLiked ? root.colors["like_color"] : root.colors["text_secondary"]
                        }
                        MouseArea {
                            id: likeMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: screenVm.item_action(row.index, "like")
                        }
                    }

                    // Play (solo completadas)
                    Rectangle {
                        visible: !screenVm.selectionMode && row.status === "completed"
                        width: 36; height: 36; radius: 18
                        color: playMa.containsMouse ? root.accentColor : "transparent"

                        Text {
                            anchors.centerIn: parent
                            text: "" // play_arrow
                            font.family: root.iconFont
                            font.pixelSize: 20
                            color: playMa.containsMouse ? root.colors["text_on_accent"] : root.colors["text_primary"]
                        }
                        MouseArea {
                            id: playMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: screenVm.play_at(row.index)
                        }
                    }

                    // Menú
                    Rectangle {
                        visible: !screenVm.selectionMode
                        width: 36; height: 36; radius: 18
                        color: menuMa.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent"

                        Text {
                            anchors.centerIn: parent
                            text: "" // more_vert
                            font.family: root.iconFont
                            font.pixelSize: 20
                            color: root.colors["text_secondary"]
                        }
                        MouseArea {
                            id: menuMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: rowMenu.popup()
                        }

                        ContextMenu {
                            id: rowMenu
                            ContextMenuItem {
                                text: "Reproducir siguiente"
                                onTriggered: screenVm.item_action(row.index, "play_next")
                            }
                            ContextMenuItem {
                                text: "Añadir a la cola"
                                onTriggered: screenVm.item_action(row.index, "add_to_queue")
                            }
                            ContextMenuItem {
                                text: "Añadir a playlist"
                                onTriggered: screenVm.item_action(row.index, "add_to_playlist")
                            }
                            ContextMenuItem {
                                text: "Eliminar descarga"
                                onTriggered: screenVm.item_action(row.index, "delete")
                            }
                        }
                    }
                }
            }

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        }

        // ── Grid de grupos (álbumes / playlists) ──────────────────────
        GridView {
            id: grid
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !screenVm.loading && screenVm.tab !== "songs" && screenVm.groups.rowCount() > 0
            model: screenVm.groups
            clip: true
            cacheBuffer: 400

            readonly property int cols: Math.max(2, Math.floor(width / 200))
            cellWidth: width / cols
            cellHeight: 216

            delegate: Item {
                id: gridCell
                width: grid.cellWidth
                height: grid.cellHeight

                required property int index
                required property string playlistId
                required property string title
                required property string subtitle
                required property string thumbnail
                required property string navigate
                required property bool selected

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingXs
                    radius: Theme.radiusLg
                    color: gridMa.containsMouse || gridCell.selected
                           ? root.colors["bg_high"] : root.colors["bg_surface"]
                    border.width: 1
                    border.color: gridCell.selected ? root.accentColor
                                  : (gridMa.containsMouse ? root.colors["border_focus"] : root.colors["border"])

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
                                text: "" // folder
                                font.family: root.iconFont
                                font.pixelSize: 36
                                color: root.colors["text_secondary"]
                            }

                            // Checkbox overlay (modo selección)
                            Rectangle {
                                visible: screenVm.selectionMode
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: Theme.spacingXs
                                width: 26; height: 26; radius: 13
                                color: gridCell.selected ? root.accentColor : "#CC000000"
                                border.width: 2
                                border.color: gridCell.selected ? root.accentColor : "#80FFFFFF"

                                Text {
                                    anchors.centerIn: parent
                                    visible: gridCell.selected
                                    text: "" // check
                                    font.family: root.iconFont
                                    font.pixelSize: 14
                                    color: root.colors["text_on_accent"]
                                }
                            }
                        }

                        Label {
                            text: gridCell.title
                            color: root.colors["text_primary"]
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.typeLabel
                            font.weight: Font.Medium
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Label {
                            text: gridCell.subtitle
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
                            if (screenVm.selectionMode)
                                screenVm.toggle_group_selected(gridCell.index)
                            else if (gridCell.navigate)
                                screenVm.navigate(gridCell.navigate)
                        }
                    }
                }
            }

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        }
    }

    // ── Confirmación de borrado ───────────────────────────────────────
    Dialog {
        id: confirmBatch
        modal: true
        anchors.centerIn: Overlay.overlay
        padding: Theme.spacingLg

        property bool isAll: false
        function openFor(all) {
            isAll = all
            open()
        }

        background: Rectangle {
            radius: Theme.radiusLg
            color: root.colors["bg_surface"]
            border.width: 1
            border.color: root.colors["border"]
        }

        contentItem: ColumnLayout {
            spacing: Theme.spacingMd

            Label {
                text: confirmBatch.isAll ? "Confirmar eliminación masiva" : "Confirmar eliminación"
                color: root.colors["text_primary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeTitle
                font.weight: Font.DemiBold
            }
            Label {
                Layout.preferredWidth: 360
                wrapMode: Text.WordWrap
                text: {
                    var target = screenVm.tab === "songs" ? "canciones descargadas"
                             : (screenVm.tab === "albums" ? "álbumes descargados con todas sus canciones"
                                                    : "playlists descargadas con todas sus canciones")
                    if (confirmBatch.isAll)
                        return "¿Eliminar TODAS las " + target + "?"
                    return "¿Eliminar las " + screenVm.selectedCount + " " + target + " seleccionadas?"
                }
                color: root.colors["text_secondary"]
                font.family: Theme.fontFamily
                font.pixelSize: Theme.typeBody
            }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: Theme.spacingSm

                HeaderButton {
                    text: "Cancelar"
                    onClicked: confirmBatch.close()
                }
                HeaderButton {
                    text: "Eliminar"
                    danger: true
                    onClicked: {
                        if (confirmBatch.isAll) screenVm.delete_all()
                        else screenVm.delete_selected()
                        confirmBatch.close()
                    }
                }
            }
        }
    }
}
