import State from "../state";

export default function connectLines(state: State, otherlineCimKey: string, busKey: string, line: Record<string, any>, lineCimKey: string, id_cnt: number) {
    let parentNode = state.busDict[busKey];
    let childNode = state.busDict[otherlineCimKey];
    // the parent of the connection shall be the one closer to a root node
    if (childNode.stepsAwayFromRootNode != -1) { // -1 is the value for not-connected elements
        if (parentNode.stepsAwayFromRootNode > childNode.stepsAwayFromRootNode) {
            // switch
            parentNode = state.busDict[otherlineCimKey];
            childNode = state.busDict[busKey];
        }
    }
    // increment and add
    childNode.stepsAwayFromRootNode = parentNode.stepsAwayFromRootNode + 1;
    let acceptedChild = parentNode.addChild(childNode, false, line["max_i_ka"], lineCimKey, id_cnt++);
    if (!acceptedChild) {
        // if this child finds no other parent, we will force-add it later
        state.tryToAddChildLaterList.push([parentNode, childNode])
    }
    
    return id_cnt;
}