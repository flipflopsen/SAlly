import Cable from "../classes/cable";

import * as SETTINGS from "../settings";

export default function scaleLineThickness(myCablesArray: Cable[]) {
  // for lines use "max_i_ka" combined with the voltage level they are at, which
  // you get from the nodes they are connected to
  // because max_i_ka * vn_kv = the maximum amount of power that can be
  // delivered by this line
  // this information is now stored in maxApparentPower for each cable

  let biggestElem = myCablesArray[0];
  myCablesArray.forEach(myElem => {
    if (biggestElem.maxApparentPower_va < myElem.maxApparentPower_va) {
      biggestElem = myElem;
    }
  });

  let sizeFactor = 1;
  if ((biggestElem.maxApparentPower_va) > 0) {
    sizeFactor = SETTINGS.MAXLINETHICKNESS / (biggestElem.maxApparentPower_va);
  }
  if(SETTINGS.SHOWDEBUGGINGINFO){
    console.log("size factor:", sizeFactor);
  }

  myCablesArray.forEach(myElem => {
    // let oldSize = myElem.size.copy();
    myElem.halfCableThickness = (sizeFactor * myElem.maxApparentPower_va) / 2;
    if (myElem.halfCableThickness < SETTINGS.MINLINETHICKNESS / 2) {
      myElem.halfCableThickness = SETTINGS.MINLINETHICKNESS / 2;
    }
  });

}
