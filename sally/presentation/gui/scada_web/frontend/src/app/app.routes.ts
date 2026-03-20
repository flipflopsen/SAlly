import {Routes} from "@angular/router";

import {GridComponent} from "./grid/grid.component";
import { DashboardComponent } from "./dashboard/dashboard.component";

export const routes: Routes = [
  {
    path: "",
    component: DashboardComponent
  },
  {
    path: "grid",
    component: GridComponent
  },
  {
    path: "dashboard",
    component: DashboardComponent
  }
];
