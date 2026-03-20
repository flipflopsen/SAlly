import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class LayoutService {

  constructor(private httpClient: HttpClient) { }

  async getLayout() {
    let layout = this.httpClient.get<string>("/api/v0/layout", { responseType: 'json' });
    return await firstValueFrom(layout);
  }

  async postLayout(layout: string) {
    let req = this.httpClient.post("/api/v0/layout", JSON.parse(layout));
    req.subscribe(res => {
      if (res) { console.log("Saving the layout was successful"); }
      else { console.log("Saving the layout failed"); }
    });
  }
}
