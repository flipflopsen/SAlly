import { Component } from '@angular/core';
import { GrafanaService } from '../grafana.service';
import { KeyValuePipe, NgFor, NgIf } from '@angular/common';
import { FontAwesomeModule } from '@fortawesome/angular-fontawesome';
import { faCaretDown, faCheck, faTimes } from '@fortawesome/free-solid-svg-icons';
import { firstValueFrom } from 'rxjs';

@Component({
  selector: 'dashboard-grafana-control',
  standalone: true,
  imports: [NgFor, KeyValuePipe, NgIf, FontAwesomeModule],
  templateUrl: './grafana-control.component.html',
  styleUrl: './grafana-control.component.scss',
})
export class GrafanaControlComponent {
  faCaretDown = faCaretDown;
  faCheck = faCheck;
  faTimes = faTimes;

  categorizedComponentIds: { [key: string]: string[] } = {};

  selectedComponents: string[] = [];

  constructor(private grafanaService: GrafanaService) {}

  ngOnInit(): void {
    this.getCategorizedIds();
  }

  getCategorizedIds(): void {
    firstValueFrom(this.grafanaService.fetchComponentIds()).then((response) => {
      let ids: string[] = response.componentIds;
      let categories: Set<string> = new Set<string>();

      for (let id of ids) {
        let category: string = id.split('-')[1];
        categories.add(category); // bus, line, load etc....
      }

      let result: Record<string, string[]> = {};
      for (let cat of categories) {
        let catIds: string[] = [];
        for (let id of ids) {
          let elem = id.split('-');
          if (elem[1] === cat){
            const paddedID = elem[0] + "-" + elem[1] + "-" + elem[2].padStart(2, "0");
            catIds.push(paddedID);
          }
        }

        catIds.sort();

        //remove padding after sort
        let unpaddedCatIds = catIds.map(paddedID => {
          let elem = paddedID.split('-');
          elem[2] = elem[2] === '00' ? '0' : elem[2].replace(/^0+/, '');
          return elem.join('-');
        });

        result[cat] = unpaddedCatIds;
      }
      this.categorizedComponentIds = result;
    });
  }

  updateInfoboard(): void {
    this.grafanaService.updateComponents(this.selectedComponents);
    this.closeModal();
  }

  removeClicked(item: string): void {
    console.log("remove clicked" + item)
    this.selectedComponents = this.selectedComponents.filter((value) => value !== item);
  }
  

  resetFilter(): void {
    this.selectedComponents = [];
  }

  openModal(): void {
    this.setBulmaActive('grafana-control-modal');
  }

  closeModal(): void {
    this.closeAllDropdowns();
    this.setBulmaUnactive('grafana-control-modal');
  }

  closeAllDropdowns(): void {
    for (let cat in this.categorizedComponentIds) {
      this.setBulmaUnactive('filter-dropdown-' + cat);
    }
  }

  toggleDropdown(id: string): void {
    this.toggleBulmaActive('filter-dropdown-' + id);
  }

  clickDropdownItem(id: string): void {
    let index: number = this.selectedComponents.indexOf(id);
    if (index === -1) {
      this.selectedComponents.push(id);
    } else {
      this.selectedComponents.splice(index, 1);
    }
  }

  toggleBulmaActive(id: string) {
    let classList: DOMTokenList | undefined =
      document.getElementById(id)?.classList;

    if (classList !== undefined) {
      if (classList.contains('is-active')) {
        this.setBulmaUnactive(id);
      } else {
        this.setBulmaActive(id);
      }
    }
  }

  setBulmaActive(id: string): void {
    let classList: DOMTokenList | undefined =
      document.getElementById(id)?.classList;

    if (classList !== undefined && !classList.contains(id)) {
      classList.add('is-active');
    }
  }

  setBulmaUnactive(id: string): void {
    let classList: DOMTokenList | undefined =
      document.getElementById(id)?.classList;

    if (classList !== undefined && classList.contains('is-active')) {
      classList.remove('is-active');
    }
  }
}
