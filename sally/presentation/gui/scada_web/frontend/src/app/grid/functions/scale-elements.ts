import Vector2D from "../classes/vector-2d";

import * as SETTINGS from "../settings";

export default function scaleElements(
  myDict: Record<string, any>,
  myMetric: any
) {
  // the elements must still fit in the grid, we don't want a new ordering of
  // elements just because one got bigger
  // scale the elements between MINELEMENTSIZE and ELEMENTSIZE, where
  // MINELEMENTSIZE is for the smallest and ELEMENTSIZE for the biggest

  // accoring to a metric, scale the size of the elements in an array while respecting ELEMENTSIZE & MINELEMENTSIZE
  let biggestElem = myDict[Object.keys(myDict)[0]];

  for (const [key, myElem] of Object.entries(myDict)) {
    if (biggestElem.info[myMetric] < myElem.info[myMetric]) {
      biggestElem = myElem;
    }
  }

  // the volume of the objects shall increase linearly with the size of their metric
  let sizeFactor = Math.sqrt(
    (
      SETTINGS.ELEMENTSIZE * SETTINGS.ELEMENTSIZE -
      SETTINGS.MINELEMENTSIZE * SETTINGS.MINELEMENTSIZE
    ) / (
      biggestElem.info[myMetric] * biggestElem.info[myMetric]
    )
  );

  for (const [key, myElem] of Object.entries(myDict)) {
    let oldSize = myElem.size.copy();
    myElem.size.x = sizeFactor * myElem.info[myMetric];
    myElem.size.y = sizeFactor * myElem.info[myMetric];

    // make sure that the element gets no smaller than MINELEMENTSIZE
    myElem.size.x = Math.max(SETTINGS.MINELEMENTSIZE, myElem.size.x);
    myElem.size.y = Math.max(SETTINGS.MINELEMENTSIZE, myElem.size.y);

    // posChange() also changes the docking port position, but not in the right
    // way since size changed. Thus set x, y new by means of center-coordinates
    // because the center does not change position during scaling
    // (outDockPosOffset is computed from dockPosOffset in posChange)
    myElem.dockPosOffset.x *= (myElem.size.x / oldSize.x);
    myElem.dockPosOffset.y *= (myElem.size.y / oldSize.y);
    myElem.posChange(new Vector2D(0,0)); // update the element
  }

}
