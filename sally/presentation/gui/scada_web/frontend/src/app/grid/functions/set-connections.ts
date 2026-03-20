import * as SETTINGS from "../settings";
import State from "../state";
import giveID from "../functions/give-id";
import connectLines from "../functions/connect-lines";


export default function setConnections(state: State) {
    // get connection-hierarchy iteratively
    // we start from busses connected to ext_grid and connect what is connected to them via the lines
    // (lines are always between 2 bus nodes only)
    let change = true; // iterate until there is no more change to the grid
    let lineKeysArray = Object.keys(state.networkConfigFile!["ac_line_segments"]);
    let wantToConnectArray: any = []; // elements that want to connect to the grid in this iteration
    let id_cnt = 0;
    let iterationCnt = 0;
    //console.log("num lines in dBase:" + (lineKeysArray.length));
    for (iterationCnt; iterationCnt < SETTINGS.MAXITERATIONS; iterationCnt++) {
        change = false;
        for (const [busKey, bus] of Object.entries(state.busDict)) {
            wantToConnectArray = [];
            // is this bus connected to a root node yet?
            if (bus.stepsAwayFromRootNode < 0) continue;

            // are there any lines left that want to connect to this bus?
            lineKeysArray.forEach((lineCimKey: any) => {
                let line = state.networkConfigFile!["ac_line_segments"][lineCimKey];
                let otherEndCimKey = line.relations[1];
                // is the bus we are looking at the start or end of the given line?
                if ((line.relations[0] == busKey)) {
                    otherEndCimKey = line.relations[1];
                    wantToConnectArray.push([line, otherEndCimKey, lineCimKey]);
                }
                if ((line.relations[1] == busKey)) {
                    otherEndCimKey = line.relations[0];
                    wantToConnectArray.push([line, otherEndCimKey, lineCimKey]);
                }
            });

            if(wantToConnectArray.length > 0) change = true;

            // connect these lines
            wantToConnectArray.forEach(([line, otherlineCimKey, lineCimKey]: any) => {
                id_cnt = connectLines(state, otherlineCimKey, busKey, line, lineCimKey, id_cnt);
                // remove used line from lineKeysArray, so that it is not considered again
                lineKeysArray.splice(lineKeysArray.indexOf(lineCimKey), 1);
            });      
        }
        if (!change) {
            break;
        }
    }
    
    if(SETTINGS.SHOWDEBUGGINGINFO){
        console.log("Done initializing child-parent relationships after", iterationCnt, "iterations");
        console.log("created " + id_cnt + " lines. Unused lines:" + (lineKeysArray));
        console.log("Number of visible wires:", giveID("wire"));    
    }

    // now see if some children are still without parents
    state.tryToAddChildLaterList.forEach(([myParent, myChild]) => {
        if (myChild.hasParent == false) {
            myParent.addChild(myChild, true);
            console.log("force added child id", myChild.id, "to parent id", myParent.id);
        }
    });
}
