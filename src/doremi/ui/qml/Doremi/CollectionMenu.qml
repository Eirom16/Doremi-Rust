import QtQuick
import QtQuick.Controls
import Doremi 1.0

ContextMenu {
    id: root
    property bool hasTracks: false
    property bool pinned: false
    property bool pinAllowed: false
    property bool downloadAllowed: false
    property bool showCopyLink: false
    property bool hasArtist: false
    property bool locallyManaged: false
    property bool showOpen: false
    property bool showPlaybackActions: true
    property bool showQueueActions: true
    signal action(string name)
    ContextMenuItem { text: "Abrir"; visible: root.showOpen; height: visible ? implicitHeight : 0; onTriggered: root.action("open") }
    ContextMenuItem { text: "Reproducir"; visible: root.showPlaybackActions; height: visible ? implicitHeight : 0; enabled: root.hasTracks; onTriggered: root.action("play") }
    ContextMenuItem { text: "Aleatorio"; visible: root.showPlaybackActions; height: visible ? implicitHeight : 0; enabled: root.hasTracks; onTriggered: root.action("shuffle") }
    ContextMenuItem { text: "Reproducir siguiente"; visible: root.showQueueActions; height: visible ? implicitHeight : 0; enabled: root.hasTracks; onTriggered: root.action("play_next") }
    ContextMenuItem { text: "Añadir a cola"; visible: root.showQueueActions; height: visible ? implicitHeight : 0; enabled: root.hasTracks; onTriggered: root.action("add_to_queue") }
    MenuSeparator { visible: root.pinAllowed || root.downloadAllowed || root.showCopyLink || root.hasArtist || root.locallyManaged; height: visible ? implicitHeight : 0 }
    ContextMenuItem { text: root.pinned ? "Desfijar de barra lateral" : "Fijar en barra lateral"; visible: root.pinAllowed; height: visible ? implicitHeight : 0; onTriggered: root.action("pin") }
    ContextMenuItem { text: "Descargar"; visible: root.downloadAllowed; height: visible ? implicitHeight : 0; enabled: root.hasTracks; onTriggered: root.action("download") }
    ContextMenuItem { text: "Copiar enlace"; visible: root.showCopyLink; height: visible ? implicitHeight : 0; onTriggered: root.action("copy_link") }
    ContextMenuItem { text: "Ir al artista"; visible: root.hasArtist; height: visible ? implicitHeight : 0; onTriggered: root.action("go_artist") }
    ContextMenuItem { text: "Renombrar"; visible: root.locallyManaged; height: visible ? implicitHeight : 0; onTriggered: root.action("rename") }
    ContextMenuItem { text: "Eliminar playlist"; visible: root.locallyManaged; height: visible ? implicitHeight : 0; onTriggered: root.action("delete") }
}
