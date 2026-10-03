import QtQuick

Item {
    id: root
    function visit(item, callback) {
        if (!item) return
        callback(item)
        var children = item.children || []
        for (var i = 0; i < children.length; ++i) visit(children[i], callback)
    }
    function captureState() {
        var state = {}
        visit(screenLoader.item, function(item) {
            if (item.objectName && item.objectName.indexOf("viewState:") === 0 && item.contentY !== undefined)
                state[item.objectName] = item.contentY
        })
        return state
    }
    function restoreState(state) {
        var target = screenLoader.item
        Qt.callLater(function() {
            if (screenLoader.item !== target) return
            visit(target, function(item) {
                if (item.objectName && state[item.objectName] !== undefined && item.contentY !== undefined)
                    item.contentY = Math.max(0, Math.min(state[item.objectName], Math.max(0, item.contentHeight - item.height)))
            })
        })
    }

    // Source and VM must be delivered as one operation. Updating two bound
    // properties independently briefly gives the old screen the new VM (or
    // vice versa), which is particularly destructive for QML routes.
    function showScreen(source, vm) {
        if (!source || !vm) {
            screenLoader.source = ""
            return
        }
        if (screenLoader.item && screenLoader.source === source) {
            screenLoader.item.screenVm = vm
            return
        }
        screenLoader.setSource(source, { "screenVm": vm })
    }

    Loader {
        id: screenLoader
        objectName: "screenLoader"
        anchors.fill: parent
        onLoaded: {
            if (item) {
                item.opacity = 0
                fadeIn.target = item
                fadeIn.start()
            }
        }
    }

    NumberAnimation {
        id: fadeIn
        property: "opacity"
        from: 0
        to: 1
        duration: 180
        easing.type: Easing.OutCubic
    }
}
