# Osprey UI — Comprehensive One-Shot Frontend Rebuild Plan

> This document captures **every source file** in the `osprey_ui/src/` directory with its exact
> content so the frontend can be recreated identically in a single pass. It also includes the
> project configuration files, dummy data integration strategy, and architecture overview.

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Project Configuration](#2-project-configuration)
3. [Dummy Data Integration Strategy](#3-dummy-data-integration-strategy)
4. [Complete Source Files](#4-complete-source-files)

---

## 1. Architecture Overview

### Tech Stack
- **React 18.2** with **TypeScript 5.9.2** (Create React App)
- **Ant Design v5.0** — UI component library
- **Zustand v3.5.2** — lightweight state management
- **React Router v5.2** — client-side routing (HashRouter not used, BrowserRouter via history)
- **Highcharts 8.1.0** — timeseries and chart visualizations
- **react-virtualized** — virtualized scrolling for event stream
- **cytoscape + cytoscape-dagre** — rules dependency graph visualization
- **dayjs** — date/time manipulation
- **axios** — HTTP client
- **CSS Modules** with CSS custom properties for theming
- **classnames** — conditional CSS class joining

### Layout
```
┌──────────────────────────────────────────────────────────┐
│ NavBar (42px, sticky top, white, 2px bottom border)       │
│ [☰ Menu]  [Logo: Osprey]                                 │
├────────────┬─────────────────────────────────────────────┤
│ Query Panel│ Right Content Area                           │
│ (420px     │  ┌─ Date Picker Bar (toggleable) ──────────┐│
│  fixed,    │  ├──────────────┬──────────────────────────┤│
│  sticky)   │  │ Charts Left  │ Charts Right              ││
│            │  │ (40%,min500) │ (flex-grow)               ││
│ QueryInput │  │              │                           ││
│ + entity/  │  │ Timeseries   │ Event Stream              ││
│   query    │  │ Top N        │ (virtualized list of      ││
│   list     │  │ Extra Charts │  EventStreamCards)        ││
│            │  │              │                           ││
└────────────┴──┴──────────────┴──────────────────────────┘
```

### Route Structure (React Router v5)
```
<Router history={history}>
  <Switch>
    <Route path="/events/:eventId" → EventPage (standalone, no NavBar)
    <Route path="*" →
      <NavBar>
        <Switch>
          /query-history       → QueryHistory
          /saved-queries       → SavedQueries
          /docs/udfs           → UdfDocsView
          /bulk-job-history    → BulkJobHistoryView
          /rules-visualizer    → RulesVisualizerView
          /                    → QueryView (main dashboard)
          /entity/:type/:id   → QueryView (entity detail mode)
          /saved-query/:id    → QueryView (saved query mode)
        </Switch>
      </NavBar>
  </Switch>
</Router>
```

### State Management (Zustand Stores)
- **QueryStore** — main query state: executedQuery, sortOrder, topNTables, charts, URL sync via history
- **ApplicationConfigStore** — app config: known features, action names, summary features, entity mappings
- **EntityStore** — selected entity, label drawer visibility
- **SavedQueryStore** — saved queries list
- **ErrorStore** — error messages set
- **LabelStore** — bulk label drawer state
- **BulkActionStore** — bulk action jobs with polling
- **RulesVisualizerStore** — graph nodes/edges for rules visualization
- **SearchParamsStateListener** — syncs URL params ↔ QueryStore bidirectionally

### Styling System
- CSS custom properties defined in `src/styles/Colors.module.css` (`:root` scope)
- Brand color: `--brand-primary: #1227ce`
- CSS Modules for component-scoped styles (`.module.css` files)
- Global Ant Design overrides in `App.module.css`
- Font sizes standardized: 12-13px body, heading sizes H1-H7

---

## 2. Project Configuration

### 2.1 Files to preserve (do NOT delete during rebuild)
- `package.json` / `package-lock.json`
- `tsconfig.json`
- `.prettierrc`
- `.env.development` / `.env.production`
- `public/index.html`
- `README.md`


---

## 3. Dummy Data Integration Strategy

The rebuilt frontend should render using the dummy data files in `example_data/`:

### 3.1 sample_actions.json (~345KB, ~1000 events)
Array of action events:
```json
{
  "send_time": "2026-05-04T14:23:45.123Z",
  "data": {
    "action_id": "uuid-string",
    "action_name": "create_post" | "login",
    "data": {
      "UserId": "username123",
      "PostText": "...",
      "IpAddress": "1.2.3.4",
      "Location": "New York, NY",
      ...
    }
  }
}
```

### 3.2 sample_execution_results.json (~1.3MB, ~4025 results)
Array of execution result objects:
```json
{
  "__time": "2026-05-04T14:23:45.123Z",
  "__action_id": "uuid-string",
  "ActionName": "create_post" | "login",
  "UserId": "username123",
  "EventType": "...",
  "PostText": "...",
  "IpAddress": "1.2.3.4",
  "Location": "New York, NY",
  "ContainsHello": true | false,
  "PostLength": 42,
  ...
}
```

### 3.3 Transformation to OspreyEvent
```typescript
// Convert execution results into OspreyEvent[] for the event stream
function transformToEvents(results: RawExecutionResult[]): OspreyEvent[] {
  return results.map((r) => ({
    id: r.__action_id,
    timestamp: r.__time,
    extracted_features: Object.fromEntries(
      Object.entries(r).filter(([k]) => !k.startsWith('__'))
    ),
  }));
}
```

### 3.4 Timeseries Computation
```typescript
// Group events by time bucket and count per bucket
function computeTimeseries(events: OspreyEvent[], granularityMs: number): TimeseriesResult[] {
  const buckets = new Map<number, number>();
  for (const event of events) {
    const ts = new Date(event.timestamp).getTime();
    const bucket = Math.floor(ts / granularityMs) * granularityMs;
    buckets.set(bucket, (buckets.get(bucket) || 0) + 1);
  }
  return Array.from(buckets.entries())
    .sort(([a], [b]) => a - b)
    .map(([ts, count]) => ({
      timestamp: new Date(ts).toISOString(),
      result: { count },
    }));
}
```

### 3.5 TopN Computation
```typescript
// Group events by a dimension, count, sort desc, take top N
function computeTopN(events: OspreyEvent[], dimension: string, limit = 10): TopNResult[] {
  const counts = new Map<string, number>();
  for (const event of events) {
    const value = String(event.extracted_features[dimension] ?? 'unknown');
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  return Array.from(counts.entries())
    .sort(([, a], [, b]) => b - a)
    .slice(0, limit)
    .map(([value, count]) => ({ dimension, value, count }));
}
```

### 3.6 Integration Approach
Replace `actions/EventActions.tsx` API calls with functions that:
1. Import the JSON files at build time (or fetch them)
2. Transform and cache the results
3. Return them in the same shape the components expect
4. Apply query filters, sort order, and pagination client-side


---

## 4. Complete Source Files

Below is every source file in `osprey_ui/src/` with its exact content.
To rebuild, recreate each file at the specified path.

### `src/App.module.css`

```css
@import './styles/Colors.module.css';

.spinner {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

:global(body) {
  font-weight: 500;
  font-size: 14px;
  color: var(--text-light-primary);
  line-height: 20px;
}

/* Global Ant Style Overrides, Use Sparingly! */

:global(:last-child.ant-collapse-item) {
  border-bottom: none;
}

:global(.ant-drawer-body) {
  padding: 0;
}

:global(textarea) {
  resize: none;
}

:global(.ant-modal-content) {
  border-radius: 8px;
}

:global(.ant-modal-header) {
  border-radius: 8px 8px 0 0;
}

:global(.ant-modal-footer) {
  border-radius: 0 0 8px 8px;
}

:global(.ant-btn) > span {
  display: flex;
  align-items: center;
}

:global(.ant-btn.ant-btn-link) {
  user-select: text !important;
}

:global(.ant-row.ant-form-item) {
  margin-bottom: 4px !important;
}

:global(.ant-col.ant-form-item-label) {
  padding-bottom: 4px;
}

:global(.ant-form-item-label) > label {
  text-transform: uppercase;
  font-weight: 600;
  font-size: 12px !important;
  color: var(--text-light-headings-primary);
}

:global(.ant-btn-link) {
  color: var(--link-primary);
}

:global(.ant-btn) > span {
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  display: block;
}

```

### `src/App.tsx`

```typescript
import * as React from 'react';
import { App as AntdApp, ConfigProvider, Spin } from 'antd';
import { Router, Switch, Route } from 'react-router-dom';

import { getApplicationConfig } from './actions/ConfigActions';
import UdfDocsView from './components/docs/UdfDocsView';
import BulkJobHistoryView from './components/bulk_job_history/BulkJobHistory';
import RulesVisualizerView from './components/rules_visualizer/RulesVisualizer';
import EntityViewBar from './components/entities/EntityViewBar';
import EventPage from './components/event_stream/EventPage';
import NavBar from './components/navigation/NavBar';
import QueryHistory from './components/query_history/QueryHistory';
import QueryView from './components/query_view/QueryView';
import SavedQueries from './components/saved_queries/SavedQueries';
import SavedQueryBar from './components/saved_queries/SavedQueryBar';
import usePromiseResult from './hooks/usePromiseResult';
import useApplicationConfigStore from './stores/ApplicationConfigStore';
import { history } from './stores/QueryStore';
import { renderFromPromiseResult } from './utils/PromiseResultUtils';

import './stores/SearchParamsStateListener';

import { Routes } from './Constants';
import styles from './App.module.css';
import { BulkActionPage } from './components/bulk_actions/BulkActionPage';

const AppRouter: React.FC = () => {
  const updateApplicationConfig = useApplicationConfigStore((state) => state.updateApplicationConfig);

  const applicationConfigResult = usePromiseResult(async () => {
    const appConfig = await getApplicationConfig();
    updateApplicationConfig(appConfig);
  });

  const theme = React.useMemo(() => {
    return {
      token: {
        colorPrimary:
          getComputedStyle(document.documentElement).getPropertyValue('--brand-primary').trim() || '#1227ce',
      },
    };
  }, []);

  return renderFromPromiseResult(applicationConfigResult, () => (
    <ConfigProvider theme={theme}>
      <AntdApp>
        <Router history={history}>
          <Switch>
            <Route path="/events/:eventId">
              <EventPage />
            </Route>
            <Route>
              <NavBar>
                <Route exact path={[Routes.SAVED_QUERY, Routes.SAVED_QUERY_LATEST]}>
                  <SavedQueryBar />
                </Route>
                <Route exact path={Routes.ENTITY}>
                  <EntityViewBar />
                </Route>
                <Switch>
                  <Route path={Routes.QUERY_HISTORY}>
                    <QueryHistory />
                  </Route>
                  <Route path={Routes.SAVED_QUERIES}>
                    <SavedQueries />
                  </Route>
                  <Route path={Routes.DOCS_UDFS}>
                    <UdfDocsView />
                  </Route>
                  <Route path={Routes.BULK_JOB_HISTORY}>
                    <BulkJobHistoryView />
                  </Route>
                  <Route path={Routes.RULES_VISUALIZER}>
                    <RulesVisualizerView />
                  </Route>
                  <Route exact path={[Routes.ENTITY, Routes.HOME, Routes.SAVED_QUERY]}>
                    <QueryView />
                  </Route>
                  <Route exact path={Routes.SAVED_QUERY_LATEST}>
                    <div className={styles.spinner}>
                      <Spin size="large" />
                    </div>
                  </Route>
                  <Route exact path={Routes.BULK_ACTION} component={BulkActionPage} />
                </Switch>
              </NavBar>
            </Route>
          </Switch>
        </Router>
      </AntdApp>
    </ConfigProvider>
  ));
};

export default AppRouter;

```

### `src/Constants.tsx`

```typescript
export const Routes = {
  HOME: '/',
  QUERY_HISTORY: '/query-history',
  SAVED_QUERIES: '/saved-queries',
  DOCS_UDFS: '/docs/udfs',
  ENTITY: '/entity/:entityType/:entityId',
  SAVED_QUERY: '/saved-query/:savedQueryId',
  SAVED_QUERY_LATEST: '/saved-query/:savedQueryId/latest',
  BULK_JOB_HISTORY: '/bulk-job-history',
  RULES_VISUALIZER: '/rules-visualizer',
  BULK_ACTION: '/bulk-action',
};

export const DATE_FORMAT = 'M/D/YYYY h:mm:ssa zz';

// These should mirror the `--status-primary` colors in Colors.module.css
export const StatusColors = {
  SUCCESS: '#3e7025',
  ERROR: '#b23a32',
  NEUTRAL: '#45464a',
};

// These should mirror colors in `Colors.module.css`
export const Colors = {
  BACKGROUND_SECONDARY_ALT: '#f2f3f5',

  TEXT_LIGHT_PRIMARY: '#45464a',

  ICON_PRIMARY: '#535a65',
  ICON_MUTED: '#9aa1ac',
};

export const BULK_LABEL_DEFAULT_LIMIT = 100000;

```

### `src/actions/BulkJobActions.tsx`

```typescript
import HTTPUtils, { HTTPResponse } from '../utils/HTTPUtils';
import { BulkJobTask } from '../types/BulkJobTypes';
import { BulkActionJob, StartBulkActionRequest, StartBulkActionResponse } from '../types/BulkActionTypes';

export async function getBulkJob(taskId: string | undefined): Promise<BulkJobTask[]> {
  // null on page load
  if (taskId == null) {
    return [];
  }

  // valid job number
  if (!isNaN(Number(taskId))) {
    const response: HTTPResponse = await HTTPUtils.get(`/bulk_history/${taskId}`);

    if (response.ok) {
      return response.data;
    }
  }

  return [];
}

// use numJobs in the future to fetch N number of jobs
export async function getLastNBulkJobs(numJobs: number = 25): Promise<BulkJobTask[]> {
  const response: HTTPResponse = await HTTPUtils.get(`/bulk_history`);

  if (!response.ok) {
    return [];
  }

  return response.data;
}

export async function startBulkAction(request: StartBulkActionRequest): Promise<StartBulkActionResponse> {
  const response: HTTPResponse = await HTTPUtils.post('/bulk_action/start', request);

  if (response.ok) {
    return response.data;
  }

  throw new Error('Failed to start bulk action: ' + response.error);
}

export async function uploadFile(url: string, file: File): Promise<void> {
  const formData = new FormData();
  formData.append('file', file);

  const response: HTTPResponse = await HTTPUtils.post(url, formData);

  if (!response.ok) {
    throw new Error('Failed to upload file: ' + response.error);
  }
}

export async function uploadCompleted(jobId: string): Promise<void> {
  const request = { job_id: jobId };

  const response: HTTPResponse = await HTTPUtils.post(`/bulk_action/upload_completed`, request);

  if (!response.ok) {
    throw new Error('Failed to complete bulk action: ' + response.error);
  }
}

export async function getJobs(): Promise<BulkActionJob[]> {
  const response: HTTPResponse = await HTTPUtils.get(`/bulk_action/jobs`);

  if (!response.ok) {
    return [];
  }

  return response.data.jobs;
}

export async function cancelJob(jobId: string): Promise<void> {
  const response: HTTPResponse = await HTTPUtils.post(`/bulk_action/jobs/${jobId}/cancel`);

  if (!response.ok) {
    throw new Error('Failed to cancel job: ' + response.error);
  }
}

```

### `src/actions/ConfigActions.tsx`

```typescript
import DefaultFeature from '../models/DefaultFeature';
import { ApplicationConfig } from '../stores/ApplicationConfigStore';
import { RawUIConfig } from '../types/ConfigTypes';
import HTTPUtils, { HTTPResponse } from '../utils/HTTPUtils';

export async function getApplicationConfig(): Promise<ApplicationConfig> {
  const response: HTTPResponse = await HTTPUtils.get('config');
  if (!response.ok) {
    throw new Error('Failed to load initial application config: ' + response.error.message);
  }

  const rawConfigData: RawUIConfig = response.data;
  const featureNameToEntityTypeMapping = new Map(Object.entries(rawConfigData.feature_name_to_entity_type_mapping));
  const entityToFeatureSetMapping = new Map();

  featureNameToEntityTypeMapping.forEach((val, key) => {
    const newFeatureSet = entityToFeatureSetMapping.has(val) ? [...entityToFeatureSetMapping.get(val), key] : [key];
    entityToFeatureSetMapping.set(val, new Set(newFeatureSet));
  });

  const knownFeatureCategories: { [key: string]: string[] } = {};

  rawConfigData.known_feature_locations.forEach((feature) => {
    const { source_path: category, name: featureName } = feature;

    if (knownFeatureCategories.hasOwnProperty(category)) {
      knownFeatureCategories[category].push(featureName);
    } else {
      knownFeatureCategories[category] = [featureName];
    }
  });

  return {
    defaultSummaryFeatures: rawConfigData.default_summary_features.map(
      (feature) => new DefaultFeature(feature.actions, feature.features)
    ),
    featureNameToEntityTypeMapping,
    featureNameToValueTypeMapping: new Map(Object.entries(rawConfigData.feature_name_to_value_type_mapping)),
    entityToFeatureSetMapping,
    externalLinks: new Map(Object.entries(rawConfigData.external_links)),
    labelInfoMapping: new Map(
      Object.entries(rawConfigData.label_info_mapping).map(([name, info]) => [
        name,
        {
          validFor: new Set(info.valid_for),
          connotation: info.connotation,
          description: info.description,
        },
      ])
    ),
    knownFeatureNames: new Set(rawConfigData.known_feature_locations.map((feature) => feature.name).sort()),
    knownFeatureCategories,
    knownActionNames: new Set(rawConfigData.known_action_names.sort()),
    currentUser: rawConfigData.current_user,
    ruleInfoMapping: new Map(Object.entries(rawConfigData.rule_info_mapping)),
  };
}

```

### `src/actions/DocActions.tsx`

```typescript
import { UdfCategory } from '../types/DocTypes';
import HTTPUtils, { HTTPResponse } from '../utils/HTTPUtils';

export async function getUdfDocs(): Promise<UdfCategory[]> {
  const response: HTTPResponse = await HTTPUtils.get('docs/udfs');

  if (!response.ok) {
    return [];
  }

  return response.data.udf_categories;
}

```

### `src/actions/EntityActions.tsx`

```typescript
import invariant from 'invariant';
import { sum } from 'lodash';

import useEntityStore from '../stores/EntityStore';
import { KeyedLabels, Label, LabelMutation, LabelMutationResult } from '../types/LabelTypes';
import { BaseQueryRequest, EventCountsByFeatureForEntityQuery } from '../types/QueryTypes';
import HTTPUtils, { HTTPResponse } from '../utils/HTTPUtils';
import { getBaseRequest } from './EventActions';

function transformLabels(labels: KeyedLabels): Label[] {
  return Object.keys(labels).map((labelName) => ({ ...labels[labelName], name: labelName }));
}

export async function getLabelsForEntity(entityId: string, entityType: string): Promise<Label[]> {
  const response: HTTPResponse = await HTTPUtils.get(`entities/labels`, {
    params: {
      entity_id: entityId,
      entity_type: entityType,
    },
  });

  if (response.ok && response.data != null) {
    return transformLabels(response.data.labels);
  }

  return [];
}

export async function getEventCountsByFeatureForEntityQuery(
  query: BaseQueryRequest,
  aggregationDimensions: string[]
): Promise<EventCountsByFeatureForEntityQuery> {
  const { entity, ...requestData } = getBaseRequest(query);
  invariant(entity != null, 'Event counts can only be fetched for entities');

  const response: HTTPResponse = await HTTPUtils.post(
    `entities/event-count-by-feature`,
    {
      ...requestData,
      granularity: 'all',
      aggregation_dimensions: aggregationDimensions /* eslint-disable-line */,
      entity,
    },
    {
      params: {
        entity_id: entity.id,
        entity_type: entity.type,
      },
    }
  );

  if (!response.ok) {
    return {};
  }

  useEntityStore.setState({ eventCountByFeature: response.data, totalEventCount: sum(Object.values(response.data)) });
  return response.data;
}

export async function updateLabelsForEntity(
  entityId: string,
  entityType: string,
  labels: LabelMutation[]
): Promise<LabelMutationResult> {
  const response: HTTPResponse = await HTTPUtils.post(
    `entities/labels`,
    {
      mutations: labels,
    },
    {
      params: {
        entity_id: entityId,
        entity_type: entityType,
      },
    }
  );

  if (!response.ok) {
    throw new Error('Label update request failed');
  }

  return { ...response.data, labels: transformLabels(response.data.labels) };
}

```

### `src/actions/EventActions.tsx`

```typescript
import { saveAs } from 'file-saver';
import { matchPath } from 'react-router';

import { history } from '../stores/QueryStore';
import { LabelMutation, LabelStatusAPIMapping } from '../types/LabelTypes';
import {
  TopNComparisonResult,
  ScanResult,
  ScanQueryRequest,
  TimeseriesResult,
  StoredExecutionResult,
  QueryRequest,
  ScanQueryOrder,
  BaseQueryRequest,
  FeatureLocations,
} from '../types/QueryTypes';
import HTTPUtils, { HTTPResponse } from '../utils/HTTPUtils';

import { BULK_LABEL_DEFAULT_LIMIT, Routes } from '../Constants';

export function getBaseRequest({
  start,
  end,
  queryFilter,
  entityFeatureFilters = new Set(),
}: BaseQueryRequest): QueryRequest {
  const entityViewMatch = matchPath<{ entityId: string; entityType: string }>(history.location.pathname, {
    path: Routes.ENTITY,
  });

  /* eslint-disable */
  const queryRequest: QueryRequest = {
    start,
    end,
    query_filter: queryFilter,
    entity: null,
  };

  if (entityViewMatch != null) {
    queryRequest.entity = {
      id: decodeURIComponent(entityViewMatch.params.entityId),
      type: decodeURIComponent(entityViewMatch.params.entityType),
      feature_filters: entityFeatureFilters.size > 0 ? [...entityFeatureFilters] : null,
    };
  }
  /* eslint-enable */

  return queryRequest;
}

export async function getTopNQueryResults(
  query: BaseQueryRequest,
  dimension: string | null,
  limit: number = 100,
  precision: number = 0
): Promise<TopNComparisonResult> {
  if (dimension === '' || dimension == null) {
    return { comparison: [], current_period: [], previous_period: [] };
  }

  const response = await HTTPUtils.post('events/topn', {
    ...getBaseRequest(query),
    dimension,
    limit,
    precision,
  });

  if (response.data.length > 0) {
    return response.data[0].result;
  }

  return response.data;
}

export async function getGroupByApproximateCountResults(
  query: BaseQueryRequest,
  dimension: string | null
): Promise<number | null> {
  if (dimension === '' || dimension == null) {
    return null;
  }

  const response = await HTTPUtils.post('events/groupby/approximate-count', {
    ...getBaseRequest(query),
    dimension,
  });
  return response.data?.count ?? null;
}

export async function getScanQueryResults(
  query: BaseQueryRequest,
  sortOrder: ScanQueryOrder,
  limit: number,
  offset?: string | null
): Promise<ScanResult> {
  const requestData: ScanQueryRequest = {
    ...getBaseRequest(query),
    order: sortOrder,
    limit,
  };

  if (offset != null) {
    requestData.next_page = offset; /* eslint-disable-line */
  }

  const response: HTTPResponse = await HTTPUtils.post('events/scan', requestData);

  if (!response.ok) return { events: [], offset: null, queryStart: null };
  return {
    events: response.data.events,
    offset: response.data.next_page,
    queryStart: response.data.next_page != null ? query.start : null,
  };
}

export async function getFeatureLocations(): Promise<FeatureLocations> {
  const response: HTTPResponse = await HTTPUtils.get('docs/feature-locations', {
    validateStatus: (status) => status === 200 || status === 401,
  });

  if (!response.ok || !response.data?.locations) return { locations: [] };
  return response.data;
}

export async function getTopNQueryResultCSV(query: BaseQueryRequest, dimension: string, limit: number): Promise<void> {
  const response: HTTPResponse = await HTTPUtils.post('events/topn/csv', {
    ...getBaseRequest(query),
    dimension,
    limit,
  });

  if (response.ok) {
    const fileBlob = new Blob([response.data], { type: 'text/csv' });
    saveAs(fileBlob, `osprey-${query.start}-${query.end}.csv`);
  } else {
    throw new Error(response.error.message);
  }
}

export async function getTimeseriesQueryResults(
  query: BaseQueryRequest,
  granularity: string
): Promise<TimeseriesResult[]> {
  const response: HTTPResponse = await HTTPUtils.post('events/timeseries', {
    ...getBaseRequest(query),
    granularity,
  });

  if (!response.ok) return [];
  return response.data;
}

export async function getDetailedEventFeatures(eventId: string): Promise<StoredExecutionResult> {
  const response: HTTPResponse = await HTTPUtils.get(`events/event/${eventId}`);

  if (!response.ok) throw new Error('Failed to load detailed event features: ' + response.error.message);
  return response.data;
}

export async function postTopBulkLabelTask(
  query: BaseQueryRequest,
  dimension: string,
  excludedEntities: Set<string>,
  entitiesToLabelCount: number,
  noLimit: boolean,
  labelMutation: LabelMutation
): Promise<number | null> {
  // The entity count is separate from the limiter; This check makes
  // sure that a limited job will expect to label the correct amount of entities.
  // If the expected count is more than 10% different from the actual count,
  // the job will fail downstream.
  if (!noLimit && entitiesToLabelCount > BULK_LABEL_DEFAULT_LIMIT) {
    entitiesToLabelCount = BULK_LABEL_DEFAULT_LIMIT;
  }
  /* eslint-disable */
  const response = await HTTPUtils.post('events/topn/bulk_label', {
    ...getBaseRequest(query),
    dimension,
    excluded_entities: [...excludedEntities],
    expected_entities: entitiesToLabelCount,
    no_limit: noLimit,
    label_name: labelMutation.label_name,
    label_status: LabelStatusAPIMapping[labelMutation.status],
    label_reason: labelMutation.reason,
    label_expiry: labelMutation.expires_at,
  });
  /* eslint-enable */
  return response.data?.task_id ?? null;
}

```

### `src/actions/QueryActions.tsx`

```typescript
import { QueryRecord, QueryState, QueryRecordRequest, TopNTable } from '../types/QueryTypes';
import HTTPUtils, { HTTPResponse } from '../utils/HTTPUtils';

export function formatQueryForRequest({ executedQuery, sortOrder, topNTables }: QueryState): QueryRecordRequest {
  return {
    /* eslint-disable */
    query_filter: executedQuery.queryFilter,
    date_range: [executedQuery.start, executedQuery.end],
    top_n: [...topNTables.values()].map((table) => table.asQueryParam()),
    sort_order: sortOrder,
    /* eslint-enable */
  };
}

export async function validateQuery(queryFilter: string): Promise<boolean> {
  const response: HTTPResponse = await HTTPUtils.post('queries/validate', {
    query_filter: queryFilter /* eslint-disable-line */,
  });
  return response.ok;
}

export async function saveQueryToHistory({
  executedQuery,
  sortOrder,
  topNTables,
  charts,
}: QueryState): Promise<QueryRecord | void> {
  if (executedQuery == null) return;
  const response: HTTPResponse = await HTTPUtils.post(
    'queries/query',
    formatQueryForRequest({ executedQuery, sortOrder, topNTables, charts })
  );

  if (!response.ok) {
    return;
  }

  return response.data;
}

export async function getQueriesHistory(userEmail?: string, before?: string): Promise<QueryRecord[]> {
  const response: HTTPResponse = await HTTPUtils.get('queries', {
    params: { before, user_email: userEmail } /* eslint-disable-line */,
  });

  if (!response.ok) {
    return [];
  }

  let data = response.data;

  return data.map((d: any) => {
    if (Array.isArray(d.top_n)) {
      d.top_n = d.top_n.map(TopNTable.fromQueryParam);
    }
    return d;
  });
}

export async function getQueryUserEmails(): Promise<string[]> {
  const response: HTTPResponse = await HTTPUtils.get('queries/user-emails');

  if (!response.ok) {
    return [];
  }

  return response.data;
}

```

### `src/actions/RulesVisualizerActions.tsx`

```typescript
import HTTPUtils, { HTTPResponse } from '../utils/HTTPUtils';

export async function getGraphJson(
  type: string,
  names: string[],
  showLabelUpstream: boolean,
  showLabelDownstream: boolean
) {
  if (type === 'label') {
    return await getLabelsViewGraphJson(names, showLabelUpstream, showLabelDownstream);
  } else if (type === 'action') {
    return await getActionsViewGraphJson(names);
  }
  return {
    errorMessage: 'Cannot formulate request: unrecognized selected feature type.',
    selectedFeature: names[0],
  };
}

async function getActionsViewGraphJson(action_names: Array<string>): Promise<any> {
  const response: HTTPResponse = await HTTPUtils.post(`/rules_visualizer/actions_view/`, { action_names });
  const selection = {
    selectedFeature: action_names[0],
    selectedFeatureType: 'Action',
  };

  if (response.ok) {
    return {
      ...response.data,
      ...selection,
      errorMessage: undefined,
    };
  }
  return {
    errorMessage: response.error.message,
    ...selection,
  };
}

async function getLabelsViewGraphJson(
  label_names: Array<string>,
  showLabelUpstream: boolean,
  showLabelDownstream: boolean
): Promise<any> {
  const response: HTTPResponse = await HTTPUtils.post(`/rules_visualizer/labels_view/`, {
    label_names,
    show_upstream: showLabelUpstream,
    show_downstream: showLabelDownstream,
  });
  const selection = {
    selectedFeature: label_names[0],
    selectedFeatureType: 'Label',
  };

  if (response.ok) {
    return {
      ...response.data,
      ...selection,
      errorMessage: undefined,
    };
  }
  return {
    errorMessage: response.error.message,
    ...selection,
  };
}

```

### `src/actions/SavedQueryActions.tsx`

```typescript
import { QueryRecord, SavedQuery, QueryState, QueryRecordRequest, TopNTable } from '../types/QueryTypes';
import HTTPUtils, { HTTPResponse } from '../utils/HTTPUtils';
import { formatQueryForRequest } from './QueryActions';

export async function createSavedQuery(queryId: string, name: string): Promise<SavedQuery> {
  /* eslint-disable-next-line */
  const response: HTTPResponse = await HTTPUtils.post('saved-queries', { query_id: queryId, name });
  if (!response.ok) {
    throw Error;
  }

  let data = response.data;
  if (Array.isArray(data.query.top_n)) {
    data.query.top_n = data.query.top_n.map(TopNTable.fromQueryParam);
  }

  return data;
}

export async function getSavedQueries(userEmail?: string, before?: string): Promise<SavedQuery[]> {
  const response: HTTPResponse = await HTTPUtils.get('saved-queries', {
    params: { before, user_email: userEmail } /* eslint-disable-line */,
  });

  if (!response.ok) {
    return [];
  }

  let data = response.data;

  return data.map((d: any) => {
    if (Array.isArray(d.query.top_n)) {
      d.query.top_n = d.query.top_n.map(TopNTable.fromQueryParam);
    }
    return d;
  });
}

export async function getSavedQuery(savedQueryId: string): Promise<SavedQuery> {
  const response: HTTPResponse = await HTTPUtils.get(`saved-queries/${savedQueryId}`);

  if (!response.ok) {
    throw Error('Saved query not found');
  }

  let data = response.data;
  if (Array.isArray(data.query.top_n)) {
    data.query.top_n = data.query.top_n.map(TopNTable.fromQueryParam);
  }

  return data;
}

export async function updateSavedQuery(
  savedQueryId: string,
  name: string,
  queryState?: QueryState
): Promise<SavedQuery> {
  const updateData: { name: string; query?: QueryRecordRequest } = { name };

  if (queryState != null) {
    updateData.query = formatQueryForRequest(queryState);
  }

  const response: HTTPResponse = await HTTPUtils.patch(`saved-queries/${savedQueryId}`, updateData);

  if (!response.ok) {
    throw Error('Error updating saved query');
  }

  let data = response.data;
  if (Array.isArray(data.query.top_n)) {
    data.query.top_n = data.query.top_n.map(TopNTable.fromQueryParam);
  }

  return data;
}

export async function getSavedQueryHistory(savedQueryId: string): Promise<QueryRecord[]> {
  const response: HTTPResponse = await HTTPUtils.get(`saved-queries/${savedQueryId}/history`);

  if (!response.ok) {
    return [];
  }

  let data = response.data;

  return data.map((d: any) => {
    if (Array.isArray(d.top_n)) {
      d.top_n = d.top_n.map(TopNTable.fromQueryParam);
    }
    return d;
  });
}

export async function deleteSavedQuery(savedQueryId: string): Promise<void> {
  const response: HTTPResponse = await HTTPUtils.delete(`saved-queries/${savedQueryId}`);

  if (!response.ok) {
    throw Error('Error deleting saved query');
  }

  return response.data;
}

export async function getSavedQueryUserEmails(): Promise<string[]> {
  const response: HTTPResponse = await HTTPUtils.get('saved-queries/user-emails');

  if (!response.ok) {
    return [];
  }

  return response.data;
}

```

### `src/assets/Logo.tsx`

```typescript
import * as React from 'react';

interface LogoProps {
  width?: number;
  height?: number;
}

const Logo = ({ width = 128, height = 32 }: LogoProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 270 74" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M82.85 57.57C78.9233 57.57 75.4875 56.7625 72.5425 55.1475C69.6292 53.5008 67.365 51.205 65.75 48.26C64.135 45.2833 63.3275 41.7842 63.3275 37.7625C63.3275 33.7092 64.135 30.21 65.75 27.265C67.365 24.2883 69.6292 21.9925 72.5425 20.3775C75.4875 18.7625 78.9233 17.955 82.85 17.955C86.8083 17.955 90.2442 18.7625 93.1575 20.3775C96.1025 21.9925 98.3667 24.2883 99.95 27.265C101.565 30.21 102.373 33.7092 102.373 37.7625C102.373 41.7842 101.565 45.2833 99.95 48.26C98.335 51.2367 96.055 53.5325 93.11 55.1475C90.1967 56.7625 86.7767 57.57 82.85 57.57ZM82.85 51.2525C86.7133 51.2525 89.7217 50.0492 91.875 47.6425C94.0283 45.2042 95.105 41.9108 95.105 37.7625C95.105 33.5825 94.0283 30.2892 91.875 27.8825C89.7533 25.4758 86.745 24.2725 82.85 24.2725C78.9867 24.2725 75.9783 25.4758 73.825 27.8825C71.6717 30.2892 70.595 33.5825 70.595 37.7625C70.595 41.9108 71.6717 45.2042 73.825 47.6425C75.9783 50.0492 78.9867 51.2525 82.85 51.2525ZM120.371 57.57C116.255 57.57 113.009 56.715 110.634 55.005C108.259 53.2633 106.976 50.8408 106.786 47.7375H113.674C113.895 49.2258 114.576 50.3342 115.716 51.0625C116.856 51.7592 118.503 52.1075 120.656 52.1075C124.298 52.1075 126.119 51.0625 126.119 48.9725C126.119 48.0858 125.834 47.405 125.264 46.93C124.725 46.455 123.807 46.0908 122.509 45.8375L116.191 44.65C110.65 43.5733 107.879 40.945 107.879 36.765C107.879 34.0733 108.94 31.9358 111.061 30.3525C113.183 28.7375 116.096 27.93 119.801 27.93C123.57 27.93 126.546 28.7533 128.731 30.4C130.948 32.015 132.183 34.3108 132.436 37.2875H125.596C125.248 35.8625 124.583 34.8333 123.601 34.2C122.651 33.535 121.274 33.2025 119.469 33.2025C117.854 33.2025 116.619 33.4558 115.764 33.9625C114.909 34.4692 114.481 35.2133 114.481 36.195C114.481 36.9233 114.75 37.5092 115.289 37.9525C115.827 38.3958 116.682 38.7283 117.854 38.95L124.266 40.185C127.18 40.755 129.317 41.705 130.679 43.035C132.04 44.365 132.721 46.1542 132.721 48.4025C132.721 51.2842 131.66 53.5325 129.539 55.1475C127.417 56.7625 124.361 57.57 120.371 57.57ZM139.564 68.4V35.5775H136.049V28.5H143.317V33.06H145.312C146.293 31.4133 147.623 30.1467 149.302 29.26C150.98 28.3733 153.007 27.93 155.382 27.93C158.295 27.93 160.765 28.5475 162.792 29.7825C164.818 30.9858 166.354 32.6958 167.399 34.9125C168.444 37.1292 168.967 39.7417 168.967 42.75C168.967 45.7583 168.444 48.3708 167.399 50.5875C166.386 52.8042 164.913 54.53 162.982 55.765C161.05 56.9683 158.723 57.57 155.999 57.57C153.846 57.57 151.993 57.1583 150.442 56.335C148.89 55.5117 147.687 54.3558 146.832 52.8675H146.642V68.4H139.564ZM154.099 51.4425C156.664 51.4425 158.596 50.6825 159.894 49.1625C161.224 47.6108 161.889 45.4733 161.889 42.75C161.889 40.0267 161.224 37.905 159.894 36.385C158.596 34.8333 156.664 34.0575 154.099 34.0575C151.851 34.0575 150.046 34.7067 148.684 36.005C147.323 37.2717 146.642 38.9975 146.642 41.1825V44.3175C146.642 46.5025 147.323 48.2442 148.684 49.5425C150.046 50.8092 151.851 51.4425 154.099 51.4425ZM176.617 57V35.5775H173.102V28.5H180.322V34.01H182.317C183.109 32.11 184.328 30.6692 185.975 29.6875C187.621 28.7058 189.506 28.215 191.627 28.215H194.002V34.295H191.295C188.698 34.295 186.766 35.0392 185.5 36.5275C184.233 38.0158 183.6 39.995 183.6 42.465V57H176.617ZM210.72 57.57C207.68 57.57 205.02 56.9683 202.74 55.765C200.492 54.53 198.75 52.8042 197.515 50.5875C196.312 48.3392 195.71 45.695 195.71 42.655C195.71 39.615 196.312 37.0025 197.515 34.8175C198.718 32.6008 200.428 30.9067 202.645 29.735C204.862 28.5317 207.458 27.93 210.435 27.93C213.348 27.93 215.85 28.5 217.94 29.64C220.03 30.7483 221.645 32.3633 222.785 34.485C223.925 36.575 224.495 39.0608 224.495 41.9425V44.4125H202.502C202.787 46.8192 203.627 48.6717 205.02 49.97C206.445 51.2367 208.329 51.87 210.673 51.87C212.414 51.87 213.823 51.5533 214.9 50.92C216.008 50.255 216.784 49.2733 217.227 47.975H224.353C223.687 50.9833 222.152 53.3425 219.745 55.0525C217.37 56.7308 214.362 57.57 210.72 57.57ZM202.692 39.615H217.703C217.449 37.6517 216.689 36.1633 215.422 35.15C214.187 34.105 212.525 33.5825 210.435 33.5825C208.377 33.5825 206.682 34.105 205.352 35.15C204.022 36.195 203.136 37.6833 202.692 39.615ZM229.424 68.4V62.7475H235.884L238.306 56.8575L225.861 28.5H233.319L241.869 48.6875H242.106L250.371 28.5H257.544L245.336 57L242.866 62.89C242.106 64.6317 241.267 65.9775 240.349 66.9275C239.462 67.9092 238.037 68.4 236.074 68.4H229.424Z"
        fill="black"
      />
      <path d="M47.5 40.5L47.5 58.3789L29.6211 40.5L47.5 40.5Z" stroke="black" strokeWidth="3" />
      <path d="M29 13.5C39.2173 13.5 47.5 21.7827 47.5 32V40.5H13.5V13.5H29Z" stroke="black" strokeWidth="3" />
    </svg>
  );
};

export default Logo;

```

### `src/components/bulk_actions/BulkActionPage.module.css`

```css
.viewContainer {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  height: 100%;
}

.content {
  padding: 25px;
  width: 100%;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 25%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 10px;
}

```

### `src/components/bulk_actions/BulkActionPage.tsx`

```typescript
import styles from './BulkActionPage.module.css';
import { BulkActionJobTable } from './BulkActionTable';
import BulkActionStartModalContainer from './BulkActionStartModal';
import useBulkActionStore from '../../stores/BulkActionStore';
import { useEffect } from 'react';

export const BulkActionPage = () => {
  const { getJobs, jobs, cancelJob, jobPollingInProgress } = useBulkActionStore();

  useEffect(() => {
    let cleanup: (() => void) | undefined;

    getJobs().then((cleanupFn) => {
      if (cleanupFn) {
        cleanup = cleanupFn;
      }
    });

    return () => {
      if (cleanup) {
        cleanup();
      }
    };
  }, []);

  return (
    <div className={styles.viewContainer}>
      <div className={styles.content}>
        <div className={styles.header}>
          <span>Start a new Bulk Action Job</span>
          <BulkActionStartModalContainer />
        </div>
        <BulkActionJobTable jobs={jobs} onCancelJob={cancelJob} jobPollingInProgress={jobPollingInProgress} />
      </div>
    </div>
  );
};

```

### `src/components/bulk_actions/BulkActionStartModal.module.css`

```css
.modal {
  :global(.ant-modal-content) {
    padding: 24px;
  }

  :global(.ant-form-item) {
    margin-bottom: 24px;
  }

  :global(.ant-upload-list) {
    margin-top: 12px;
  }
}

:global(.ant-upload-drag-container .ant-btn) {
  height: 60px;
}

```

### `src/components/bulk_actions/BulkActionStartModal.tsx`

```typescript
import React, { useState } from 'react';
import { App, Modal, Form, Input, Select, Upload, Button } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import type { UploadFile, UploadProps } from 'antd/es/upload/interface';
import type { FormInstance } from 'antd/es/form';
import styles from './BulkActionStartModal.module.css';
import { max, set } from 'lodash';
import useBulkActionStore from '../../stores/BulkActionStore';

const { TextArea } = Input;
const { Option } = Select;

interface WorkflowOption {
  value: string;
  label: string;
}

interface JobFormValues {
  jobName: string;
  jobDescription: string;
  workflow: string;
  customWorkflowInput?: string;
  file: File;
  entityType: string;
}

interface JobUploadModalProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (values: JobFormValues) => void;
  initialValues?: Partial<JobFormValues>;
}

const workflowOptions: WorkflowOption[] = [
  { value: 'workflow1', label: 'Test Workflow' },
  { value: 'custom', label: 'Custom Workflow' },
];

const BulkActionStartModal: React.FC<JobUploadModalProps> = ({ open, onCancel, onSubmit, initialValues }) => {
  const { modal } = App.useApp();
  const [form] = Form.useForm<JobFormValues>();
  const [customWorkflow, setCustomWorkflow] = useState<boolean>(false);
  const [fileSelected, setFileSelected] = useState<File | null>(null);

  const handleWorkflowChange = (value: string): void => {
    setCustomWorkflow(value === 'custom');
  };

  const handleSubmit = async (): Promise<void> => {
    try {
      const values: JobFormValues = (await form.validateFields()) as JobFormValues;
      if (fileSelected != null) {
        values.file = fileSelected;
      }
      onSubmit(values as JobFormValues);

      form.resetFields();
      setFileSelected(null);
      setCustomWorkflow(false);
    } catch (error) {
      console.error('Validation failed:', error);
    }
  };

  const normFile = (e: any): UploadFile[] => {
    if (Array.isArray(e)) {
      return e;
    }
    return e?.fileList || [];
  };

  // Custom validation rules
  const validationRules = {
    jobName: [
      { required: true, message: 'Please enter job name' },
      { max: 100, message: 'Job name cannot exceed 100 characters' },
    ],
    jobDescription: [
      { required: true, message: 'Please enter job description' },
      { max: 500, message: 'Job description cannot exceed 500 characters' },
    ],
    workflow: [{ required: true, message: 'Please select or enter workflow' }],
    customWorkflowInput: [
      { required: true, message: 'Please enter custom workflow' },
      { max: 100, message: 'Custom workflow cannot exceed 100 characters' },
    ],
    file: [],
    entityType: [{ required: true, message: 'Please select entity type' }],
  };

  // File upload configuration
  const uploadProps: UploadProps = {
    beforeUpload: (file) => {
      // ~10 million rows of bigint entity-ids in a CSV file would be around 250MB
      const isValidSize = file.size ? file.size / 1024 / 1024 / 1024 < 250 : false; // 250MB limit
      if (!isValidSize) {
        modal.error({
          title: 'File too large',
          content: 'File size must be less than 250MB',
        });
      }
      setFileSelected(file);
      return false; // Prevent automatic upload
    },
    accept: '.csv', // Restrict file types,
    multiple: false,
    showUploadList: false,
    type: 'drag',
  };

  return (
    <Modal
      title="Create New Job"
      open={open}
      onCancel={() => {
        form.resetFields();
        setFileSelected(null);
        setCustomWorkflow(false);
        onCancel();
      }}
      onOk={handleSubmit}
      width={600}
      className={styles.modal}
    >
      <Form<JobFormValues> form={form} layout="vertical" requiredMark="optional" initialValues={initialValues}>
        <Form.Item name="jobName" label="Job Name" rules={validationRules.jobName}>
          <Input placeholder="Enter job name" />
        </Form.Item>

        <Form.Item name="jobDescription" label="Job Description" rules={validationRules.jobDescription}>
          <TextArea placeholder="Enter job description" rows={4} />
        </Form.Item>

        <Form.Item name="entityType" label="Entity Type" rules={validationRules.entityType}>
          <Select placeholder="Select entity type">
            <Option value="user">User</Option>
            <Option value="guild">Guild</Option>
          </Select>
        </Form.Item>

        <Form.Item name="workflow" label="Workflow" rules={validationRules.workflow}>
          <Select onChange={handleWorkflowChange} placeholder="Select workflow">
            {workflowOptions.map((option) => (
              <Option key={option.value} value={option.value}>
                {option.label}
              </Option>
            ))}
          </Select>
        </Form.Item>

        {customWorkflow && (
          <Form.Item name="customWorkflowInput" label="Custom Workflow" rules={validationRules.customWorkflowInput}>
            <Input placeholder="Enter custom workflow" />
          </Form.Item>
        )}

        <Form.Item name="file" label="Upload File" getValueFromEvent={normFile} rules={validationRules.file}>
          <Upload {...uploadProps}>
            <Button icon={<UploadOutlined />}>Click to Upload</Button>
          </Upload>
          <div>{fileSelected?.name}</div>
        </Form.Item>
      </Form>
    </Modal>
  );
};

const BulkActionStartModalContainer = () => {
  const { modal } = App.useApp();
  const [visible, setVisible] = useState(false);
  const bulkActions = useBulkActionStore();

  const handleOpenModal = () => {
    setVisible(true);
  };

  const handleCloseModal = () => {
    setVisible(false);
  };

  const handleSubmit = async (values: JobFormValues) => {
    const workflow = values.workflow === 'custom' ? values.customWorkflowInput : values.workflow;
    if (!workflow) {
      modal.error({
        title: 'Workflow is required',
        content: 'Please select or enter a workflow',
      });
      return;
    }
    await bulkActions.startBulkAction({
      job_name: values.jobName,
      job_description: values.jobDescription,
      workflow_name: workflow,
      file_name: values.file.name,
      file: values.file,
      entity_type: values.entityType,
    });

    setVisible(false);

    await bulkActions.getJobs();
  };

  return (
    <>
      <Button type="primary" onClick={handleOpenModal}>
        Create New Job
      </Button>
      <BulkActionStartModal open={visible} onCancel={handleCloseModal} onSubmit={handleSubmit} />
    </>
  );
};

export default BulkActionStartModalContainer;

```

### `src/components/bulk_actions/BulkActionTable.module.css`

```css
.tableContainer {
  width: 100%;
  overflow-x: auto;
  margin-top: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  border-radius: 8px;
}

.jobTable {
  width: 100%;
  border-collapse: collapse;
  background-color: white;
  font-size: 14px;
}

.tableHeader {
  background-color: #f8f9fa;
  border-bottom: 2px solid #dee2e6;
}

.tableHeader th {
  padding: 12px 16px;
  text-align: left;
  font-weight: 600;
  color: #495057;
}

.tableRow {
  border-bottom: 1px solid #dee2e6;
}

.tableRow:hover {
  background-color: #f8f9fa;
}

.tableCell {
  padding: 12px 16px;
}

.descriptionCell {
  max-width: 300px;
  white-space: normal;
  word-wrap: break-word;
}

.statusBadge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.statusCompleted {
  background-color: #e6f4ea;
  color: #1b873f;
}

.statusInProgress {
  background-color: #fff3e0;
  color: #ff9800;
}

.statusFailed {
  background-color: #ffebee;
  color: #d32f2f;
}

.statusDefault {
  background-color: #f8f9fa;
  color: #495057;
}

.actionsContainer {
  display: flex;
  gap: 8px;
}

.actionButton {
  padding: 6px 12px;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.pauseButton {
  background-color: #007bff;
}

.pauseButton:hover {
  background-color: #0056b3;
}

.deleteButton {
  background-color: #dc3545;
}

.deleteButton:hover {
  background-color: #c82333;
}

.disabledButton {
  background-color: #ccc;
  cursor: not-allowed;
}

.disabledButton:hover {
  background-color: #ccc;
}

.inProgress {
  background-color: #f0f7f4;
}

```

### `src/components/bulk_actions/BulkActionTable.tsx`

```typescript
import React from 'react';

import type { BulkActionJob } from '../../types/BulkActionTypes';

import styles from './BulkActionTable.module.css';
import CopyLinkButton from '../common/CopyLinkButton';
import { Spin } from 'antd';

interface JobTableProps {
  jobs?: BulkActionJob[];
  onCancelJob: (jobId: string) => void;
  jobPollingInProgress: boolean;
}

function isJobInProgress(job: BulkActionJob): boolean {
  return job.status === 'processing' || job.status === 'uploaded' || job.status === 'parsing';
}

export const BulkActionJobTable: React.FC<JobTableProps> = ({ jobs = [], onCancelJob, jobPollingInProgress }) => {
  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusClass = (status: string): string => {
    switch (status) {
      case 'completed':
        return styles.statusCompleted;
      case 'processing':
      case 'uploaded':
      case 'parsing':
        return styles.statusInProgress;
      case 'failed':
      case 'cancelled':
        return styles.statusFailed;
      default:
        return styles.statusDefault;
    }
  };

  const getStatusDisplay = (job: BulkActionJob) => {
    switch (job.status) {
      case 'completed':
        return 'Completed';
      case 'processing':
        return 'Processing';
      case 'uploaded':
      case 'pending_upload':
        return 'Uploaded & Pending ';
      case 'parsing':
        return 'Setting up job';
      case 'failed':
        return 'Failed';
      case 'cancelled':
        return 'Cancelled';
      default:
        return 'Unknown';
    }
  };

  return (
    <div className={styles.tableContainer}>
      <table className={styles.jobTable}>
        <thead>
          <tr className={styles.tableHeader}>
            <th>Job ID</th>
            <th>Job Name</th>
            <th>Job Description</th>
            <th>Workflow</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Created By</th>
            <th>Created At</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job: BulkActionJob, index: number) => (
            <tr key={job.id || index} className={`${styles.tableRow} ${isJobInProgress(job) ? styles.inProgress : ''}`}>
              <td className={styles.tableCell}>{job.id}</td>
              <td className={`${styles.tableCell} ${styles.descriptionCell}`}>{job.name}</td>
              <td className={`${styles.tableCell} ${styles.descriptionCell}`}>{job.description}</td>
              <td className={styles.tableCell}>{job.action_workflow_name}</td>
              <td className={styles.tableCell}>
                <span className={`${styles.statusBadge} ${getStatusClass(job.status)}`}>{getStatusDisplay(job)}</span>
                {jobPollingInProgress && isJobInProgress(job) && <Spin size="small" />}
              </td>
              <td className={styles.tableCell}>
                {job.processed_rows ?? 0}/{job.total_rows ?? 0} actions processed
              </td>
              <td className={styles.tableCell}>{job.user_id}</td>
              <td className={styles.tableCell}>{formatDate(job.created_at)}</td>
              <td className={styles.tableCell}>
                <div className={styles.actionsContainer}>
                  <button
                    className={`${styles.actionButton} ${styles.deleteButton} ${
                      job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled'
                        ? styles.disabledButton
                        : ''
                    }`}
                    onClick={() => onCancelJob(job.id)}
                    disabled={job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled'}
                  >
                    Cancel
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

```

### `src/components/bulk_actions/Types.tsx`

```typescript
export interface Job {
  id?: number | string;
  description: string;
  status: 'Completed' | 'In Progress' | 'Failed' | string;
  createdAt: string;
}

```

### `src/components/bulk_job_history/BulkHistoryCard.tsx`

```typescript
import styles from './BulkJobHistory.module.css';
import { BulkJobTask, FormattedBulkJobTask } from '../../types/BulkJobTypes';
import Text, { TextSizes, TextColors } from '../../uikit/Text';
import PropertyTable from '../common/PropertyTable';

interface BulkJobTitleProps {
  user: string;
  action: string;
  timestamp: Date;
}

export const BulkJobTitle = ({ user, action, timestamp }: BulkJobTitleProps) => {
  return (
    <div className={styles.cardTitle}>
      <Text size={TextSizes.SMALL} color={TextColors.LIGHT_HEADINGS_SECONDARY}>
        <b>{user}</b> {action} {timestamp.toString()}
      </Text>
    </div>
  );
};

interface BulkHistoryCardProps {
  task: BulkJobTask;
  index: number;
}

const BulkHistoryCard = ({ task, index }: BulkHistoryCardProps) => {
  if (task == null) return null;
  const formatted_task: FormattedBulkJobTask = new FormattedBulkJobTask(task);

  const body: Record<string, string> = {};
  // We need to use the FormattedBulkJobTask to make sure the properties are ordered for the UI.
  // Normal typescript properties in interfaces aren't consistently ordered :(
  for (const [key, val] of formatted_task.getMap()) {
    body[key] = val;
  }

  return (
    <div key={index} className={styles.bulkJobHistoryCard}>
      <BulkJobTitle user={task.initiated_by} action="created job on " timestamp={new Date(task.created_at * 1000)} />
      <PropertyTable
        className={styles.contentTable}
        shouldWrapText={true}
        entries={[body]}
        renderValue={([key, value]) => {
          if (key.toUpperCase().endsWith('FILTER')) {
            return (
              <a title="Click to view in Osprey" href={formatted_task.getQueryUrl()}>
                {value}
              </a>
            );
          }
          return value;
        }}
      />
    </div>
  );
};

export default BulkHistoryCard;

```

### `src/components/bulk_job_history/BulkHistoryMultiView.tsx`

```typescript
import usePromiseResult from '../../hooks/usePromiseResult';
import { renderFromPromiseResult } from '../../utils/PromiseResultUtils';
import { getLastNBulkJobs } from '../../actions/BulkJobActions';
import styles from './BulkJobHistory.module.css';
import BulkHistoryCard from './BulkHistoryCard';

const BulkHistoryMultiView = () => {
  const viewContent = usePromiseResult(getLastNBulkJobs);

  return renderFromPromiseResult(viewContent, (bulkHistoryCards) => (
    <div className={styles.listContainer}>
      {bulkHistoryCards.map((value, index) => (
        <BulkHistoryCard task={value} index={index} />
      ))}
    </div>
  ));
};

export default BulkHistoryMultiView;

```

### `src/components/bulk_job_history/BulkHistorySingleView.tsx`

```typescript
import usePromiseResult from '../../hooks/usePromiseResult';
import { renderFromPromiseResult } from '../../utils/PromiseResultUtils';
import { getBulkJob } from '../../actions/BulkJobActions';
import styles from './BulkJobHistory.module.css';
import BulkHistoryCard from './BulkHistoryCard';

interface BulkHistoryPanelProps {
  taskId: string | undefined;
}

const BulkHistorySingleView = ({ taskId }: BulkHistoryPanelProps) => {
  const viewContent = usePromiseResult(() => getBulkJob(taskId), [taskId]);
  return renderFromPromiseResult(viewContent, (bulkHistoryCards) => (
    <div className={styles.listContainer}>
      {bulkHistoryCards.map((value, index) => (
        <BulkHistoryCard task={value} index={index} />
      ))}
    </div>
  ));
};

export default BulkHistorySingleView;

```

### `src/components/bulk_job_history/BulkJobHistory.module.css`

```css
.viewContainer {
  height: 100%;
  width: 100%;
  background-color: var(--background-primary);
  display: flex;
  overflow: hidden;
}

.bulkJobHistoryCard {
  padding: 4px;
  display: flex;
  flex-direction: column;
  border-bottom: 1px var(--divider) solid;
}

.cardTitle {
  display: flex;
  flex-direction: column;
  padding: 4px;
  background-color: var(--background-secondary);
  align-items: flex-start;
  border-radius: 8px;
}

.margin {
  display: flex;
  flex-direction: column;
  margin-left: 4px;
  margin-bottom: 4px;
}

.content {
  width: 100%;
  max-width: 1300px;
  display: flex;
  margin: 0 auto;
}

.header {
  padding: 16px;
  border-bottom: 1px var(--divider) solid;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}

.bulkHistoryContainer {
  max-height: 100%;
  max-width: 900px;
  width: 100%;
  flex-grow: 1;
  background-color: var(--background-primary);
  border-left: 1px solid var(--divider);
  border-right: 1px solid var(--divider);
  display: flex;
  flex-direction: column;
}

.compactBulkHistoryContainer {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: 500px;
  min-height: 255px;
  max-height: 450px;
  width: 70%;
  margin: 12px;
  border: 1px solid var(--divider);
  border-radius: 8px;
}

.compactHeader {
  height: 40px;
  padding: 8px;
  display: flex;
  align-items: center;
  background-color: var(--background-secondary);
  border-bottom: 1px solid var(--divider);
}

.cardHeaderBase {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}

.searchBar {
  width: 40%;
  margin-bottom: 2px;
  justify-content: right;
  display: flex;
  flex-direction: column;
}

.listContainer {
  overflow-y: auto;
  overflow-anchor: none;
}

.contentTable {
  width: auto;
  display: flex;
  flex-direction: column;
}

```

### `src/components/bulk_job_history/BulkJobHistory.tsx`

```typescript
import * as React from 'react';

import { Input } from 'antd';
import SavedQueriesIcon from '../../uikit/icons/SavedQueriesIcon';
import IconHeader from '../common/IconHeader';
import Text, { TextSizes } from '../../uikit/Text';
import useErrorStore from '../../stores/ErrorStore';
import BulkHistorySingleView from './BulkHistorySingleView';
import BulkHistoryMultiView from './BulkHistoryMultiView';

import styles from './BulkJobHistory.module.css';

const BulkJobHistoryView = () => {
  const [taskId, setTaskId] = React.useState<string | undefined>();

  const clearErrors = useErrorStore((state) => state.clearErrors);

  const handleSearch = async (taskId: string) => {
    clearErrors();
    if (!isNaN(Number(taskId))) {
      setTaskId(taskId);
    }
  };

  return (
    <div className={styles.viewContainer}>
      <div className={styles.content}>
        <div className={styles.bulkHistoryContainer}>
          <div className={styles.header}>
            <IconHeader size={TextSizes.H4} icon={<SavedQueriesIcon />} title="Bulk Job History" />
            <Input.Search
              className={styles.searchBar}
              placeholder="Please enter a valid integer ID"
              onSearch={handleSearch}
              enterButton
            />
          </div>
          <BulkHistoryMultiView />
        </div>
        <div className={styles.compactBulkHistoryContainer}>
          <div className={styles.compactHeader}>
            <Text size={TextSizes.H5}>Find Single Bulk Job</Text>
          </div>
          <BulkHistorySingleView taskId={taskId} />
        </div>
      </div>
    </div>
  );
};

export default BulkJobHistoryView;

```

### `src/components/bulk_label_drawer/BulkLabelDrawer.module.css`

```css
.collapsableList {
  display: flex;
  flex-direction: column;
  margin-bottom: 16px;
}

.exclamationIcon {
  color: var(--warning-primary);
  height: 20px;
  width: 20px;
  margin: 0 4px;
}

.listHeader {
  height: 40px;
  width: 100%;
  display: flex;
  flex-direction: row;
  border-left: 4px solid var(--divider);
  background-color: var(--background-secondary);
  border-radius: 2px 2px 0 0;
  align-items: center;
  justify-content: space-between;
}

.listHeaderClosed {
  border-radius: 2px;
}

.listWrapper > div {
  height: auto !important;
}

```

### `src/components/bulk_label_drawer/BulkLabelDrawer.tsx`

```typescript
import * as React from 'react';
import { ExclamationCircleOutlined } from '@ant-design/icons';
import { Drawer, notification, Modal } from 'antd';
import shallow from 'zustand/shallow';

import { getGroupByApproximateCountResults, postTopBulkLabelTask } from '../../actions/EventActions';
import useLabelStore from '../../stores/LabelStore';
import useQueryStore from '../../stores/QueryStore';
import { LabelMutation } from '../../types/LabelTypes';
import LabelForm from '../common/LabelForm';
import EntityDrawer from '../entities/LabelDrawer';

import styles from './BulkLabelDrawer.module.css';

interface BulkLabelDrawerContentProps {
  onCancel: (supressConfirmationModal: boolean) => void;
  onEntityUnchecked: (entityUnchecked: boolean) => void;
}

const BulkLabelDrawerContent = ({ onCancel, onEntityUnchecked }: BulkLabelDrawerContentProps) => {
  const [bulkLabelEntityType, bulkLabelFeatureName] = useLabelStore(
    (state) => [state.bulkLabelEntityType, state.bulkLabelFeatureName],
    shallow
  );
  const executedQuery = useQueryStore((state) => state.executedQuery);
  const entityFeatureFilters = useQueryStore((state) => state.entityFeatureFilters);
  const [entityCount, setEntityCount] = React.useState(0);
  const [entityCountString, setEntityCountString] = React.useState('[CALCULATING...]');
  const calculateApproximateCount = () => {
    getGroupByApproximateCountResults({ ...executedQuery, entityFeatureFilters }, bulkLabelFeatureName)
      .then((value) => {
        if (!value) {
          setEntityCountString('[COULD NOT CALCULATE]');
        } else {
          setEntityCountString(value.toLocaleString());
          setEntityCount(value);
        }
      })
      .catch((err) => {
        console.error(err);
        setEntityCountString('[COULD NOT CALCULATE]');
      });
  };
  React.useEffect(calculateApproximateCount, []);

  const [showChildDrawer, setShowChildDrawer] = React.useState(false);

  const handleChildDrawerClose = () => {
    setShowChildDrawer(false);
  };

  const handleSubmit = async (labelMutation: LabelMutation, noLimit: boolean) => {
    if (bulkLabelFeatureName == null) return;

    noLimit = noLimit ?? false;
    const taskId = await postTopBulkLabelTask(
      { ...executedQuery, entityFeatureFilters },
      bulkLabelFeatureName,
      new Set(), // excluded entities; removing for optimization purposes
      entityCount,
      noLimit,
      labelMutation
    );

    if (taskId === null) {
      notification.error({
        message: 'Bulk Label Task Failed to Start',
        description: `Task Failed`,
      });
    } else {
      notification.success({
        message: 'Bulk Label Task Started',
        description: `A bulk label task with id ${taskId} has been started.`,
      });
      onCancel(true);
    }
  };

  return (
    <>
      <>
        <div className={styles.__invalid_headerLeft}>
          <ExclamationCircleOutlined className={styles.exclamationIcon} />
          <span>This contains approximately {entityCountString} unique entities.</span>
        </div>
        <LabelForm
          entityType={bulkLabelEntityType}
          onCancel={() => onCancel(false)}
          onSubmit={(labelMutation, no_limit) => handleSubmit(labelMutation, no_limit)}
          isBulkLabel={true}
        />
      </>
      <EntityDrawer childDrawerProps={{ isVisible: showChildDrawer, onDrawerClose: handleChildDrawerClose }} />
    </>
  );
};

const BulkLabelDrawer: React.FC = () => {
  const [showBulkLabelDrawer, updateShowBulkLabelDrawer] = useLabelStore(
    (state) => [state.showBulkLabelDrawer, state.updateShowBulkLabelDrawer],
    shallow
  );

  const [showConfirmModal, setShowConfirmModal] = React.useState(false);
  const [entitiesHaveBeenUnchecked, setEntitiesHaveBeenUnchecked] = React.useState(false);

  const handleDrawerClose = (supressConfirmationModal: boolean) => {
    if (!entitiesHaveBeenUnchecked || supressConfirmationModal) {
      updateShowBulkLabelDrawer(false, null, null);
    } else {
      setShowConfirmModal(true);
    }
  };

  const handleConfirmationOk = () => {
    setShowConfirmModal(false);
    updateShowBulkLabelDrawer(false, null, null);
  };

  const handleConfirmationCancel = () => {
    setShowConfirmModal(false);
  };

  return (
    <Drawer
      width={450}
      title="Bulk Edit Labels"
      open={showBulkLabelDrawer}
      onClose={() => {
        handleDrawerClose(true);
      }}
      destroyOnClose
    >
      <BulkLabelDrawerContent onCancel={handleDrawerClose} onEntityUnchecked={setEntitiesHaveBeenUnchecked} />
      <Modal
        title="Are you sure you want to close?"
        open={showConfirmModal}
        onOk={handleConfirmationOk}
        onCancel={handleConfirmationCancel}
      >
        <p>You have some entities deselected and you'll lose the state if you close!</p>
      </Modal>
    </Drawer>
  );
};

export default BulkLabelDrawer;

```

### `src/components/bulk_label_drawer/BulkLabelDrawerList.module.css`

```css
.virtualizedList {
  border-top: 1px solid var(--divider);
}

.listItem {
  background-color: var(--background-secondary);
  border-bottom: 1px solid var(--divider);
  padding-left: 16px;
  justify-content: flex-start;
}

```

### `src/components/bulk_label_drawer/BulkLabelDrawerList.tsx`

```typescript
import * as React from 'react';
import { Button, List, Checkbox } from 'antd';
import { CheckboxChangeEvent } from 'antd/lib/checkbox';
import { AutoSizer, List as VList, ListRowProps } from 'react-virtualized';
import shallow from 'zustand/shallow';

import useLabelStore from '../../stores/LabelStore';
import { TopNResult } from '../../types/QueryTypes';

import styles from './BulkLabelDrawerList.module.css';

const BulkLabelDrawerList = ({
  entitiesToLabel,
  excludedEntities,
  onRowEntityClick,
  onRowCheckboxChange,
}: {
  entitiesToLabel: TopNResult[];
  excludedEntities: Set<string>;
  onRowEntityClick: (value: string) => void;
  onRowCheckboxChange: (e: CheckboxChangeEvent, value: string) => void;
}) => {
  const [bulkLabelEntityType, bulkLabelFeatureName] = useLabelStore(
    (state) => [state.bulkLabelEntityType, state.bulkLabelFeatureName],
    shallow
  );

  const handleCheckboxChange = (e: CheckboxChangeEvent, value: string) => {
    onRowCheckboxChange(e, value);
  };

  const renderListRows = ({ key, index, style }: ListRowProps) => {
    if (bulkLabelEntityType == null || bulkLabelFeatureName == null) return null;
    const item = entitiesToLabel[index];
    const value = item?.result[0]?.[bulkLabelFeatureName];

    return (
      <List.Item className={styles.listItem} key={key} style={style}>
        <Checkbox
          onChange={(e) => handleCheckboxChange(e, String(value))}
          checked={!excludedEntities.has(String(value))}
        />
        <Button
          type="link"
          onClick={() => onRowEntityClick(String(value))}
        >{`${bulkLabelEntityType} / ${value}`}</Button>
      </List.Item>
    );
  };

  return (
    <AutoSizer>
      {({ width }) => (
        <VList
          className={styles.virtualizedList}
          width={width}
          height={400}
          rowCount={entitiesToLabel.length}
          rowHeight={40}
          rowRenderer={renderListRows}
        />
      )}
    </AutoSizer>
  );
};

export default BulkLabelDrawerList;

```

### `src/components/charts/Chart.module.css`

```css
.chartWrapper {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--divider);
  border-radius: 4px;
  margin: 8px;
}

.chartWrapper:first-child {
  padding-top: 6px;
}

.chartWrapper :global(.ant-table-cell) {
  padding: 6px !important;
}

.chartWrapper :global(.ant-table-column-sorters) {
  padding: 0 !important;
}

.buttonWrapper {
  display: flex;
  flex-direction: column;
  margin-right: 8px;
}

.buttonWrapper button {
  margin: 2px;
  height: 24px;
}

.inputWrapper {
  display: flex;
  align-items: center;
}

.textArea {
  flex: 1;
  margin: 8px;
}

```

### `src/components/charts/Chart.tsx`

```typescript
import * as React from 'react';

import useQueryStore from '../../stores/QueryStore';
import Timeseries from '../timeseries/Timeseries';
import { Input } from 'antd';
import { Chart as ChartData } from '../../types/QueryTypes';
import OspreyButton, { ButtonColors } from '../../uikit/OspreyButton';

import styles from './Chart.module.css';

const Chart = ({ index }: { index: number }) => {
  const [chart, updateChart] = useQueryStore((state) => [state.charts[index], state.updateChart]);
  const [text, setText] = React.useState(chart.query);

  React.useEffect(() => setText(chart.query), [chart]);

  return (
    <div className={styles.chartWrapper}>
      <Timeseries extraQuery={chart.query} />
      <div className={styles.inputWrapper}>
        <Input.TextArea
          className={styles.textArea}
          value={text}
          onChange={(e) => setText(e.target.value)}
          spellCheck="false"
        />
        <div className={styles.buttonWrapper}>
          <OspreyButton onClick={() => updateChart(index, new ChartData(chart.query, true))}>Yeet</OspreyButton>
          <OspreyButton
            color={ButtonColors.DARK_BLUE}
            onClick={() => updateChart(index, new ChartData(text, chart.deleted))}
          >
            Submit
          </OspreyButton>
        </div>
      </div>
    </div>
  );
};

export default Chart;

```

### `src/components/charts/Charts.module.css`

```css
.chartsPanel {
  border-top: 2px solid var(--divider);
}

```

### `src/components/charts/Charts.tsx`

```typescript
import * as React from 'react';
import Panel from '../common/Panel';
import TimeseriesIcon from '../../uikit/icons/TimeseriesIcon';
import OspreyButton from '../../uikit/OspreyButton';
import useQueryStore from '../../stores/QueryStore';
import { Chart } from '../../types/QueryTypes';
import { Empty } from 'antd';
import styles from './Charts.module.css';
import ChartComponent from './Chart';

const Charts: React.FC = () => {
  const [charts, addChart] = useQueryStore((state) => [state.charts, state.addChart]);

  const renderCharts = () => {
    return (
      <div>
        {charts
          .map((chart, index) => ({ chart, index }))
          .reverse()
          .filter(({ chart, index }) => !chart.deleted)
          .map(({ chart, index }) => {
            return <ChartComponent key={index} index={index} />;
          })}
      </div>
    );
  };

  return (
    <Panel
      className={styles.chartsPanel}
      title="Extra Charts"
      icon={<TimeseriesIcon />}
      titleRight={<OspreyButton onClick={() => addChart(new Chart('', false))}>Add Chart</OspreyButton>}
    >
      {renderCharts()}
    </Panel>
  );
};

export default Charts;

```

### `src/components/common/CopyLinkButton.tsx`

```typescript
import * as React from 'react';
import { CheckCircleOutlined, LinkOutlined } from '@ant-design/icons';
import { message, Button } from 'antd';
import { copyText } from '../../lib/copyText';

interface CopyLinkButtonProps {
  link: string;
}

const CopyLinkButton = ({ link }: CopyLinkButtonProps) => {
  const [showCopySuccess, setShowCopySuccess] = React.useState(false);

  React.useEffect(() => {
    let timeout: NodeJS.Timeout | undefined;
    if (showCopySuccess) {
      timeout = setTimeout(() => {
        setShowCopySuccess(false);
      }, 1000);
    }

    return () => {
      if (timeout != null) {
        clearTimeout(timeout);
      }
    };
  }, [showCopySuccess]);

  const handleCopyLink = async () => {
    try {
      await copyText(link);
    } catch (err) {
      message.error(`Error copying text to clipboard: ${err}`);
      return;
    }
    message.success('Link copied to clipboard', 1);
    setShowCopySuccess(true);
  };

  return (
    <Button
      onClick={handleCopyLink}
      icon={showCopySuccess ? <CheckCircleOutlined /> : <LinkOutlined />}
      type="link"
      size="small"
    />
  );
};

export default CopyLinkButton;

```

### `src/components/common/ExternalLinkButton.module.css`

```css
.icon {
  transform: rotateY(180deg);
  font-size: 12px;
}

.iconWrapper {
  height: 14px;
  width: 14px;
  display: flex;
}

```

### `src/components/common/ExternalLinkButton.tsx`

```typescript
import * as React from 'react';
import { SelectOutlined } from '@ant-design/icons';
import { Button } from 'antd';
import classNames from 'classnames';

import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import OspreyButton from '../../uikit/OspreyButton';

import styles from './ExternalLinkButton.module.css';

interface ExternalLinkButtonProps {
  entityType: string;
  entityId: string;
  className?: string;
  icon?: boolean;
}

const ExternalLinkButton = ({ entityType, entityId, className, icon = false }: ExternalLinkButtonProps) => {
  const externalLinks = useApplicationConfigStore((state) => state.externalLinks);
  const externalLink = externalLinks.get(entityType);
  if (externalLink == null) return null;
  const externalLinkFormatted = externalLink.replace('{entity_id}', encodeURIComponent(entityId));

  if (icon) {
    return (
      <Button
        className={classNames(styles.iconWrapper, className)}
        icon={<SelectOutlined className={styles.icon} />}
        style={{ height: 14, width: 14 }}
        type="link"
        target="_blank"
        href={externalLinkFormatted}
      />
    );
  }

  return (
    <OspreyButton style={{ paddingTop: 6 }} className={className} target="_blank" href={externalLinkFormatted}>
      More Info
    </OspreyButton>
  );
};

export default ExternalLinkButton;

```

### `src/components/common/Feature.module.css`

```css
@keyframes wiggleShort {
  0% {
    transform: rotate(0deg);
  }

  50% {
    transform: rotate(2deg);
  }

  100% {
    transform: rotate(-2deg);
  }
}

@keyframes wiggleMedium {
  0% {
    transform: rotate(0deg);
  }

  50% {
    transform: rotate(1deg);
  }

  100% {
    transform: rotate(-1deg);
  }
}

@keyframes wiggleLong {
  0% {
    transform: rotate(0deg);
  }

  50% {
    transform: rotate(0.25deg);
  }

  100% {
    transform: rotate(-0.25deg);
  }
}

.selected {
  color: #8e5ea2 !important;
}

.selectedShort {
  composes: selected;
  animation: wiggleShort 0.25s infinite;
}

.selectedMedium {
  composes: selected;
  animation: wiggleMedium 0.25s infinite;
}

.selectedLong {
  composes: selected;
  animation: wiggleLong 0.25s infinite;
}

.null {
  color: var(--text-light-disabled);
}

```

### `src/components/common/Feature.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';
import shallow from 'zustand/shallow';

import useQueryStore from '../../stores/QueryStore';
import OspreyButton, { ButtonColors, ButtonHeights, ButtonWeights } from '../../uikit/OspreyButton';
import Text, { TextColors, TextSizes, TextWeights } from '../../uikit/Text';
import { addFeaturesToQueryFilter } from '../../utils/QueryUtils';
import { openNewQueryWindow } from '../../utils/SearchParamUtils';

import styles from './Feature.module.css';

interface CommonFeatureProps {
  featureName: string;
  onClick?: () => void;
  className?: string;
  isEntity?: boolean;
  textSelectable?: boolean;
  isFeatureNameOnly?: boolean;
}

type SelectableFeatureProps = CommonFeatureProps & {
  value: string | null;
};

const SelectableFeature = ({
  featureName,
  value,
  onClick,
  className,
  isEntity = false,
  textSelectable = true,
  isFeatureNameOnly = false,
}: SelectableFeatureProps): React.ReactElement => {
  const [queuedQueryFilters, updateQueuedQueryFilters] = useQueryStore(
    (state) => [state.queuedQueryFilters, state.updateQueuedQueryFilters],
    shallow
  );
  const [isSelected, setIsSelected] = React.useState(false);

  React.useEffect(() => {
    if (isSelected && queuedQueryFilters.length === 0) {
      setIsSelected(false);
    }
  }, [isSelected, queuedQueryFilters.length]);

  const handleFeatureClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    const feature = { value, featureName };

    if (e.shiftKey) {
      const filteredFeatures = queuedQueryFilters.filter((queuedFilter) => {
        return queuedFilter.value !== value || queuedFilter.featureName !== featureName;
      });
      const featureNotYetQueued = filteredFeatures.length === queuedQueryFilters.length;

      if (featureNotYetQueued) {
        setIsSelected(true);
        updateQueuedQueryFilters([...queuedQueryFilters, feature]);
        return;
      }
      // if queued and selected, deselect. if queued and not yet selected, don't add or remove
      if (isSelected) {
        setIsSelected(false);
        updateQueuedQueryFilters(filteredFeatures);
      }
    } else if (e.ctrlKey || e.metaKey) {
      openNewQueryWindow(addFeaturesToQueryFilter([feature]));
    } else {
      onClick?.();
    }

    return false;
  };

  const getSelectedClass = (): string => {
    if (value == null) {
      return styles.null;
    }

    if (value.length < 7) {
      return styles.selectedShort;
    } else if (value.length < 20) {
      return styles.selectedMedium;
    }

    return styles.selectedLong;
  };

  const renderValue = (value: string | null) => {
    // If the value is null, we want the ui to render the string "null".
    if (value == null) return 'null';
    if (isFeatureNameOnly)
      return (
        <Text size={TextSizes.H6} color={TextColors.LIGHT_HEADINGS_PRIMARY} weight={TextWeights.BOLD}>
          {featureName}
        </Text>
      );
    if (featureName !== 'ActionName') return value;

    return (
      <Text size={TextSizes.H6} color={TextColors.LIGHT_HEADINGS_PRIMARY} weight={TextWeights.BOLD}>
        {value}
      </Text>
    );
  };

  const getFeatureTitle = () => {
    if (isFeatureNameOnly) return featureName;
    if (isEntity) return '';
    return value ?? 'null';
  };

  return (
    <OspreyButton
      className={classNames(className, { [getSelectedClass()]: isSelected })}
      style={{ padding: 0 }}
      onClick={handleFeatureClick}
      color={value == null ? ButtonColors.LINK_DISABLED : ButtonColors.LINK_BLUE}
      height={ButtonHeights.SHORT}
      weight={isEntity ? ButtonWeights.SEMIBOLD : ButtonWeights.NORMAL}
      title={getFeatureTitle()}
      textSelectable={textSelectable}
    >
      {renderValue(value)}
    </OspreyButton>
  );
};

type FeatureProps = CommonFeatureProps & {
  value: unknown;
};

const Feature = ({ value, ...props }: FeatureProps): React.ReactElement => {
  return <SelectableFeature value={value == null ? null : String(value)} {...props} />;
};

export default Feature;

```

### `src/components/common/FeatureName.module.css`

```css
.featureNameButton {
  padding: 0;
  transition: 0.25s ease all;
}

.featureName {
  max-width: 100%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.disabled {
  pointer-events: none;
  cursor: default;
}

.disabled:hover {
  color: var(--link-primary);
}

```

### `src/components/common/FeatureName.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';
import shallow from 'zustand/shallow';

import useQueryStore from '../../stores/QueryStore';
import OspreyButton, { ButtonColors, ButtonHeights } from '../../uikit/OspreyButton';
import Text, { TextSizes, TextWeights } from '../../uikit/Text';

import styles from './FeatureName.module.css';
import { TopNTable } from '../../types/QueryTypes';

interface FeatureNameProps {
  featureName: string;
}

const FeatureName = ({ featureName }: FeatureNameProps): React.ReactElement => {
  const [topNTables, updateTopNTables] = useQueryStore((state) => [state.topNTables, state.updateTopNTables], shallow);

  const handleAddTopNTable = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (e.shiftKey) {
      const newTopNTables = new Map();
      // Maps retain ordering based on insertion; We are basing our insertion ordering off of that fact
      newTopNTables.set(featureName, new TopNTable(featureName));
      topNTables.forEach((table, key) => newTopNTables.set(key, table));
      updateTopNTables(newTopNTables);
    }
  };

  return (
    <OspreyButton
      className={classNames(styles.featureNameButton, { [styles.disabled]: topNTables.has(featureName) })}
      color={ButtonColors.LINK_GRAY}
      height={ButtonHeights.SHORT}
      onClick={handleAddTopNTable}
      title={featureName}
    >
      <Text className={styles.featureName} size={TextSizes.SMALL} weight={TextWeights.NORMAL}>
        {featureName}
      </Text>
    </OspreyButton>
  );
};

export default FeatureName;

```

### `src/components/common/FilterPill.module.css`

```css
.filterPillBase {
  height: 20px;
  border-radius: 8px;
  padding: 2px 8px;
  border: none;
  font-size: 12px;
}

.filterPill {
  composes: filterPillBase;
  border: 2px solid var(--divider);
}

.filterPill:hover {
  color: var(--brand-primary);
  border: 2px solid var(--divider);
}

.filterPillSelected {
  composes: filterPillBase;
  background-color: var(--link-muted);
  color: var(--brand-primary);
  border: 2px solid transparent;
}

.filterPillSelected:hover {
  background-color: var(--link-muted);
  color: var(--brand-primary);
  border: 2px solid transparent;
}

.closeCircleIcon {
  margin-left: 8px;
}

```

### `src/components/common/FilterPill.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';

import OspreyButton from '../../uikit/OspreyButton';
import CloseCircleIcon from '../../uikit/icons/CloseCircleIcon';

import styles from './FilterPill.module.css';

interface FilterPillProps {
  filterName: string;
  count?: number;
  onClick?: (filterName: string) => void;
  isSelected: boolean;
  className?: string;
}

const FilterPill = ({ filterName, count, onClick, isSelected, className }: FilterPillProps) => {
  if (count === 0) return null;

  const handleFeatureClick = () => {
    onClick?.(filterName);
  };

  return (
    <OspreyButton
      onClick={handleFeatureClick}
      className={classNames(isSelected ? styles.filterPillSelected : styles.filterPill, className)}
    >
      {`${filterName} ${count != null ? `(${count.toLocaleString()})` : ''}`}
      {isSelected ? <CloseCircleIcon className={styles.closeCircleIcon} /> : null}
    </OspreyButton>
  );
};

export default FilterPill;

```

### `src/components/common/IconDropdownMenu.module.css`

```css
.menuIcon {
  padding: 0;
  height: auto;
}

```

### `src/components/common/IconDropdownMenu.tsx`

```typescript
import * as React from 'react';

import DropdownMenu, { MenuOption } from '../../uikit/DropdownMenu';
import OspreyButton, { ButtonColors } from '../../uikit/OspreyButton';
import HorizontalMenuIcon from '../../uikit/icons/HorizontalMenuIcon';

import styles from './IconDropdownMenu.module.css';

interface IconDropdownMenuProps {
  options: MenuOption[];
}

const IconDropdownMenu = ({ options }: IconDropdownMenuProps) => {
  return (
    <DropdownMenu options={options}>
      <OspreyButton className={styles.menuIcon} color={ButtonColors.LINK_GRAY}>
        <HorizontalMenuIcon />
      </OspreyButton>
    </DropdownMenu>
  );
};

export default IconDropdownMenu;

```

### `src/components/common/IconHeader.module.css`

```css
.header {
  display: flex;
  flex-direction: row;
  align-items: center;
}

.iconWrapper {
  margin-right: 8px;
  display: inline-flex;
}

```

### `src/components/common/IconHeader.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';

import Text, { TextSizes } from '../../uikit/Text';

import styles from './IconHeader.module.css';

interface IconHeaderProps {
  icon: React.ReactElement;
  size: (typeof TextSizes)[keyof typeof TextSizes];
  title: string;
  className?: string;
}

const IconHeader = ({ icon, size, title, className }: IconHeaderProps) => {
  return (
    <div>
      <Text size={size} className={classNames(styles.header, className)}>
        <span className={styles.iconWrapper}>{icon}</span>
        {title}
      </Text>
    </div>
  );
};

export default IconHeader;

```

### `src/components/common/LabelForm.module.css`

```css
.labelForm {
  margin: 0 16px 16px;
}

.buttonWrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

.submitButton {
  margin-left: 8px;
}

.permanentAlert {
  margin-top: 8px;
}

.permanentDescription {
  margin-bottom: 8px;
}

```

### `src/components/common/LabelForm.tsx`

```typescript
import * as React from 'react';
import { Alert, Checkbox, Form, Input, Select } from 'antd';
import { Store } from 'antd/lib/form/interface';
import dayjs from 'dayjs';

import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import { LabelStatus, LabelMutation, Label } from '../../types/LabelTypes';
import { IntervalOptions } from '../../types/QueryTypes';
import OspreyButton, { ButtonColors } from '../../uikit/OspreyButton';
import Text, { TextSizes, TextWeights } from '../../uikit/Text';

import styles from './LabelForm.module.css';

const ExpiryOptions = {
  ONE_SECOND: 'oneSecond',
  ONE_HOUR: 'hour',
  ONE_DAY: 'day',
  ONE_WEEK: 'week',
  TWO_WEEKS: 'twoWeeks',
  ONE_MONTH: 'month',
  TWO_MONTHS: 'twoMonths',
  THREE_MONTHS: 'threeMonths',
  PERMANENT: 'permanent',
};

interface LabelFormProps {
  label?: Label;
  title?: React.ReactNode;
  onCancel: () => void;
  onSubmit: (labelMutation: LabelMutation, noLimit: boolean) => void;
  entityType?: string | null;
  isSubmitting?: boolean;
  isBulkLabel?: boolean;
}

const LabelForm = ({
  label,
  title,
  onSubmit,
  onCancel,
  entityType,
  isSubmitting = false,
  isBulkLabel = false,
}: LabelFormProps) => {
  const labelInfoMapping = useApplicationConfigStore((state) => state.labelInfoMapping);
  const isAddLabelForm = label == null;
  const initialExpiry = isAddLabelForm ? ExpiryOptions.PERMANENT : ExpiryOptions.TWO_WEEKS;

  const [expiry, setExpiry] = React.useState(initialExpiry);
  const [checked, setChecked] = React.useState(false);
  const [noLimit, setNolimit] = React.useState(false);
  const [labelStatus, setLabelStatus] = React.useState(LabelStatus.MANUALLY_ADDED);

  const [form] = Form.useForm();

  const handleSubmit = (values: Store) => {
    const name = label?.name ?? values.name;
    const status = isAddLabelForm ? values.status : LabelStatus.MANUALLY_REMOVED;

    const labelMutation: LabelMutation = {
      label_name: name /* eslint-disable-line */,
      status,
      reason: values.reason,
    };

    if (values.expires_at !== ExpiryOptions.PERMANENT) {
      const expiresAt: keyof Partial<typeof IntervalOptions> = values.expires_at;
      const {
        durationConstructor: [number, unit],
      } = IntervalOptions[expiresAt];
      /* eslint-disable-next-line */
      labelMutation.expires_at = dayjs.utc().add(number, unit).format();
    }

    onSubmit(labelMutation, noLimit);
  };

  const getSelectOptionsForEntity = (): Array<{ label: string; value: string }> => {
    const validLabels: Array<{ label: string; value: string }> = [];
    if (entityType == null) return validLabels;

    labelInfoMapping.forEach((value, key) => {
      if (value.validFor.has(entityType)) {
        validLabels.push({ value: key, label: key });
      }
    });

    return validLabels;
  };

  const renderAddFormFields = () => {
    if (!isAddLabelForm) return null;

    return (
      <>
        <Form.Item
          style={{ marginBottom: 8 }}
          label="Label Name"
          name="name"
          rules={[{ required: true, message: 'Please select a label' }]}
        >
          <Select showSearch options={getSelectOptionsForEntity()} />
        </Form.Item>
        <Form.Item
          label="Status"
          name="status"
          initialValue={isBulkLabel ? LabelStatus.ADDED : LabelStatus.MANUALLY_ADDED}
        >
          <Select<LabelStatus>
            onChange={setLabelStatus}
            options={[
              { value: LabelStatus.MANUALLY_ADDED, label: 'Manually Added' },
              { value: LabelStatus.MANUALLY_REMOVED, label: 'Manually Removed' },
              { value: LabelStatus.ADDED, label: 'Added' },
              { value: LabelStatus.REMOVED, label: 'Removed' },
            ]}
          />
        </Form.Item>
      </>
    );
  };

  const renderLimitField = () => {
    if (!isBulkLabel) return null;

    return (
      <Form.Item className={styles.permanentAlert}>
        <Alert
          message="Info"
          description={
            <>
              <div className={styles.permanentDescription}>
                Standard bulk jobs have a limit of 100,000 entities to label. Selecting this will remove the limit.
              </div>
              <div className={styles.permanentDescription}>
                NOTE: No limit bulk jobs may take significantly longer to process.
              </div>
              <Checkbox checked={noLimit} onChange={(e) => setNolimit(e.target.checked)}>
                <Text tag="span" weight={TextWeights.NORMAL}>
                  NO LIMIT
                </Text>
              </Checkbox>
            </>
          }
          type="info"
          showIcon
        />
      </Form.Item>
    );
  };

  const shouldShowPermanentWarning =
    expiry === ExpiryOptions.PERMANENT && (!isAddLabelForm || labelStatus !== LabelStatus.MANUALLY_ADDED);

  const renderPermanentWarning = () => {
    if (!shouldShowPermanentWarning) return null;

    return (
      <Form.Item className={styles.permanentAlert}>
        <Alert
          message="Warning"
          description={
            <>
              <div className={styles.permanentDescription}>
                A permanent expiry means that Osprey cannot apply the removed label again. Please take care when
                selecting this option.
              </div>
              <Checkbox checked={checked} onChange={(e) => setChecked(e.target.checked)}>
                <Text tag="span" weight={TextWeights.SEMIBOLD}>
                  I understand and want to remove this label permanently.
                </Text>
              </Checkbox>
            </>
          }
          type="warning"
          showIcon
        />
      </Form.Item>
    );
  };

  return (
    <div className={styles.labelForm}>
      <Form form={form} onFinish={handleSubmit} layout="vertical">
        {title}
        {renderAddFormFields()}
        <Form.Item
          style={{ marginBottom: 8 }}
          label="Reason"
          name="reason"
          rules={[{ required: true, message: 'Please input a reason' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item label="Expiration" name="expires_at" initialValue={initialExpiry}>
          <Select<string>
            onChange={setExpiry}
            options={[
              { value: ExpiryOptions.ONE_DAY, label: 'One Day' },
              { value: ExpiryOptions.ONE_WEEK, label: 'One Week' },
              { value: ExpiryOptions.TWO_WEEKS, label: 'Two Weeks' },
              { value: ExpiryOptions.ONE_MONTH, label: 'One Month' },
              { value: ExpiryOptions.TWO_MONTHS, label: 'Two Months' },
              { value: ExpiryOptions.THREE_MONTHS, label: 'Three Months' },
              { value: ExpiryOptions.PERMANENT, label: 'Permanent' },
              { value: ExpiryOptions.ONE_SECOND, label: 'Instant' },
            ]}
          />
        </Form.Item>
        {renderPermanentWarning()}
        {renderLimitField()}
        <Form.Item>
          <div className={styles.buttonWrapper}>
            <OspreyButton htmlType="button" onClick={onCancel}>
              Cancel
            </OspreyButton>
            <OspreyButton
              disabled={shouldShowPermanentWarning && !checked}
              className={styles.submitButton}
              color={isAddLabelForm ? ButtonColors.DARK_BLUE : ButtonColors.DANGER_RED}
              htmlType="submit"
              loading={isSubmitting}
            >
              {isAddLabelForm ? 'Submit' : 'Remove Label'}
            </OspreyButton>
          </div>
        </Form.Item>
      </Form>
    </div>
  );
};

export default LabelForm;

```

### `src/components/common/LabelTag.module.css`

```css
.labelTag {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  padding: 0 4px;
  border-radius: 2px;
  height: 24px;
}

.positive {
  background-color: var(--success-muted);
  color: var(--success-primary);
}

.negative {
  background-color: var(--error-muted);
  color: var(--error-primary);
}

.neutral {
  background-color: var(--background-tertiary);
}

.dottedOutline {
  border-style: dashed;
  border-width: 2px;
  background-color: transparent;
  line-height: 20px;
}

.grayedOut {
  opacity: 0.55 !important;
}

.manualIcon {
  margin-right: 4px;
}

```

### `src/components/common/LabelTag.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';

import { Label, LabelStatus, LabelConnotation } from '../../types/LabelTypes';
import Text, { TextSizes, TextWeights } from '../../uikit/Text';
import ManuallyAddedIcon from '../../uikit/icons/ManuallyAddedIcon';
import ManuallyRemovedIcon from '../../uikit/icons/ManuallyRemovedIcon';
import { isTimestampPast } from '../../utils/DateUtils';

import { StatusColors } from '../../Constants';
import styles from './LabelTag.module.css';

const LabelConnotationClassName = {
  [LabelConnotation.POSITIVE]: styles.positive,
  [LabelConnotation.NEGATIVE]: styles.negative,
  [LabelConnotation.NEUTRAL]: styles.neutral,
};

const ConnotationToColorMapping = {
  [LabelConnotation.POSITIVE]: StatusColors.SUCCESS,
  [LabelConnotation.NEGATIVE]: StatusColors.ERROR,
  [LabelConnotation.NEUTRAL]: StatusColors.NEUTRAL,
};

interface LabelTagProps {
  label: Label;
  connotation: LabelConnotation;
  className?: string;
}

function isRemoved(status: LabelStatus): boolean {
  return status === LabelStatus.REMOVED || status === LabelStatus.MANUALLY_REMOVED;
}

function isManual(status: LabelStatus): boolean {
  return status === LabelStatus.MANUALLY_ADDED || status === LabelStatus.MANUALLY_REMOVED;
}

function isExpired(label: Label): boolean {
  return Object.values(label.reasons).every(
    (reason) => reason.expires_at != null && isTimestampPast(reason.expires_at)
  );
}

function getTagIcon(status: LabelStatus, color: string): React.ReactNode {
  if (!isManual(status)) return null;

  if (isRemoved(status)) {
    return <ManuallyRemovedIcon color={color} className={styles.manualIcon} />;
  }

  return <ManuallyAddedIcon color={color} className={styles.manualIcon} />;
}

const LabelTag = ({ label, connotation, className }: LabelTagProps): React.ReactElement => {
  return (
    <Text
      size={TextSizes.SMALL}
      weight={TextWeights.SEMIBOLD}
      className={classNames(
        styles.labelTag,
        LabelConnotationClassName[connotation],
        { [styles.dottedOutline]: isRemoved(label.status), [styles.grayedOut]: isExpired(label) },
        className
      )}
    >
      {getTagIcon(label.status, ConnotationToColorMapping[connotation])}
      {label.name}
    </Text>
  );
};

export default LabelTag;

```

### `src/components/common/ModalFooter.module.css`

```css
.footer {
  display: flex;
  justify-content: flex-end;
}

```

### `src/components/common/ModalFooter.tsx`

```typescript
import * as React from 'react';

import OspreyButton, { ButtonColors, ButtonWeights } from '../../uikit/OspreyButton';

import styles from './ModalFooter.module.css';

interface ModalFooterProps {
  onOK: () => void;
  onCancel: () => void;
  isSubmitting?: boolean;
  isDisabled?: boolean;
}

const ModalFooter = ({ onOK, onCancel, isSubmitting = false, isDisabled = false }: ModalFooterProps) => {
  return (
    <div className={styles.footer}>
      <OspreyButton key="cancel" onClick={onCancel} weight={ButtonWeights.BOLD}>
        Cancel
      </OspreyButton>
      <OspreyButton
        disabled={isDisabled}
        loading={isSubmitting}
        key="ok"
        color={ButtonColors.DARK_BLUE}
        weight={ButtonWeights.BOLD}
        onClick={onOK}
      >
        Apply
      </OspreyButton>
    </div>
  );
};

export default ModalFooter;

```

### `src/components/common/OptionLabelWithInfo.module.css`

```css
.optionLabelWithInfo {
  display: flex;
  align-items: center;
}

.optionLabelWithInfo .feature {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

```

### `src/components/common/OptionLabelWithInfo.tsx`

```typescript
import { InfoCircleOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';

import { Key } from 'rc-select/lib/interface/generator';

import { OptionInfoMapping } from '../../stores/ApplicationConfigStore';

import styles from './OptionLabelWithInfo.module.css';

function OptionLabelWithInfo({ option, optionInfoMapping }: { option: Key; optionInfoMapping: OptionInfoMapping }) {
  if (typeof option !== 'number' && optionInfoMapping.get(option)) {
    return (
      <div className={styles.optionLabelWithInfo} key={option}>
        <div className={styles.feature}>{option}</div>
        <Tooltip title={optionInfoMapping.get(option)} placement="right" overlayStyle={{ maxWidth: 500 }}>
          <InfoCircleOutlined />
        </Tooltip>
      </div>
    );
  } else {
    return <>{option}</>;
  }
}

export default OptionLabelWithInfo;

```

### `src/components/common/Panel.module.css`

```css
.panel {
  background-color: var(--background-primary);
  position: relative;
}

.panelHeader {
  padding: 8px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 2px solid var(--divider);
}

.title {
  margin-left: 8px;
}

.titleLeft {
  display: flex;
  align-items: center;
}

```

### `src/components/common/Panel.tsx`

```typescript
import * as React from 'react';
import { Empty } from 'antd';
import classNames from 'classnames';

import { TextSizes } from '../../uikit/Text';
import IconHeader from './IconHeader';

import styles from './Panel.module.css';

interface PanelProps {
  children?: React.ReactNode;
  className?: string;
  title: string;
  titleRight?: React.ReactNode;
  icon: React.ReactElement;
  collapsible?: boolean;
}

const Panel = ({ children, className, title, icon: Icon, titleRight }: PanelProps) => {
  const panelContent = children == null ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} /> : children;

  return (
    <div className={classNames(styles.panel, className)}>
      <div className={styles.panelHeader}>
        <IconHeader className={styles.titleLeft} size={TextSizes.H5} icon={Icon} title={title} />
        {titleRight}
      </div>
      {panelContent}
    </div>
  );
};

export default Panel;

```

### `src/components/common/PropertyTable.module.css`

```css
.propertyTable {
  width: 100%;
}

.row {
  display: flex;
  align-items: flex-start;
  height: 100%;
  border-radius: 8px;
}

.darkRow {
  composes: row;
  background-color: var(--background-secondary);
}

.keyValuePair {
  flex-grow: 1;
  max-width: 33.3%;
  text-align: left;
  padding: 4px;
}

.keyValuePair:first-child {
  padding-left: 8px;
}

.highlightedCell {
  background-color: var(--link-light-hover);
  border-radius: 8px;
}

.key {
  height: 16px;
  display: flex;
  align-items: center;
}

.highlightDot {
  margin-left: 4px;
}

.value {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  padding-right: 2px;
}

.value_wrapped {
  overflow: hidden;
  white-space: normal;
  overflow-wrap: break-word;
  padding-right: 2px;
}

```

### `src/components/common/PropertyTable.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';
import { chunk } from 'lodash';

import Text, { TextSizes } from '../../uikit/Text';
import BrandDot from '../../uikit/icons/BrandDot';

import styles from './PropertyTable.module.css';

export type Entries = Record<string, string>;
type Entry = [string, string];

interface PropertyTableProps {
  className?: string;
  entries: Entries[];
  columns?: number;
  renderKey?: (entry: Entry) => React.ReactNode;
  renderValue?: (entry: Entry) => React.ReactNode;
  shouldHighlightCell?: (entry: Entry) => boolean;
  shouldWrapText?: boolean;
}

const PropertyTable = ({
  className,
  entries,
  columns = 3,
  renderKey,
  renderValue,
  shouldHighlightCell,
  shouldWrapText = false,
}: PropertyTableProps) => {
  const entriesAsTuples = entries.map((entry) => Object.entries(entry));
  let currentRowIndex = 0;

  const renderRow = (entryTuple: Entry[], index: number) => {
    return (
      <div key={index} className={(index + 1) % 2 === 0 ? styles.darkRow : styles.row}>
        {entryTuple.map((entry) => {
          const [key, value] = entry;
          const highlightCell = shouldHighlightCell?.(entry);

          return (
            <div className={classNames(styles.keyValuePair, { [styles.highlightedCell]: highlightCell })} key={key}>
              <Text className={styles.key} size={TextSizes.SMALL}>
                {renderKey != null ? renderKey(entry) : key}
                {highlightCell ? <BrandDot className={styles.highlightDot} /> : null}
              </Text>
              <div
                title={shouldWrapText ? undefined : value}
                className={shouldWrapText ? styles.value_wrapped : styles.value}
              >
                {renderValue != null ? renderValue(entry) : value}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const renderBlock = (entryBlock: Entry[]) => {
    return chunk(entryBlock, columns).map((block) => {
      const row = renderRow(block, currentRowIndex);
      currentRowIndex++;
      return row;
    });
  };

  return <div className={classNames(styles.propertyTable, className)}>{entriesAsTuples.map(renderBlock)}</div>;
};

export default PropertyTable;

```

### `src/components/common/QueryCards.module.css`

```css
.cardHeaderBase {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}

.cardHeader {
  composes: cardHeaderBase;
  background-color: var(--background-primary);
  padding: 8px 16px;
  height: 48px;
}

.cardHeaderCompact {
  composes: cardHeaderBase;
  background-color: var(--background-secondary-alt);
  padding: 0 16px;
}

.cardBody {
  padding: 4px 16px;
  background-color: var(--background-secondary-alt);
}

.additionalInfo {
  text-transform: capitalize;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
  color: var(--text-light-secondary);
  font-size: 12px;
  line-height: 16px;
}

.overflowTopNList {
  padding-left: 12px;
  margin-bottom: 0;
}

.divider {
  width: 100%;
  margin: 4px auto;
  height: 1px;
  background-color: var(--divider);
}

.queryFilterExpand {
  max-height: 60px;
  line-height: 20px;
  overflow: hidden;
}

:global(pre) {
  margin-bottom: 0;
  white-space: pre-wrap;
  overflow-wrap: break-word;
}

```

### `src/components/common/QueryCards.tsx`

```typescript
import * as React from 'react';
import dayjs from 'dayjs';

import { QueryRecord } from '../../types/QueryTypes';
import Expand, { ExpandButton } from '../../uikit/Expand';
import OverflowTooltip from '../../uikit/OverflowTooltip';
import Text, { TextSizes, TextColors } from '../../uikit/Text';
import { localizeAndFormatTimestamp } from '../../utils/DateUtils';
import QueryFilter from './QueryFilter';

import { DATE_FORMAT } from '../../Constants';
import styles from './QueryCards.module.css';

interface QueryCardActionDataProps {
  user: string;
  action: string;
  timestamp: number;
}

export const QueryCardActionData = ({ user, action, timestamp }: QueryCardActionDataProps) => {
  return (
    <Text size={TextSizes.SMALL} color={TextColors.LIGHT_SECONDARY}>
      <b>{user}</b> {action} {dayjs.unix(timestamp).format(DATE_FORMAT)}
    </Text>
  );
};

interface QueryCardHeaderProps {
  children: React.ReactNode;
  isCompact?: boolean;
}

export const QueryCardHeader = ({ children, isCompact = false }: QueryCardHeaderProps) => {
  return <div className={isCompact ? styles.cardHeaderCompact : styles.cardHeader}>{children}</div>;
};

interface QueryCardBodyProps {
  query: QueryRecord;
  queryFilterPlaceholder?: React.ReactNode;
  intervalCopy: string;
  isCompact?: boolean;
}

export const QueryCardBody = ({
  query,
  queryFilterPlaceholder = null,
  intervalCopy,
  isCompact = false,
}: QueryCardBodyProps) => {
  const getOverflowTooltipContent = (content: React.ReactNode) => {
    const topNTables =
      query.top_n.length === 0 ? null : (
        <>
          <div>Top N Tables:</div>
          <ul className={styles.overflowTopNList}>
            {query.top_n.map((table) => table.dimension && <li key={table.dimension}>{table.dimension}</li>)}
          </ul>
        </>
      );

    return (
      <>
        {content}
        {topNTables}
      </>
    );
  };

  const renderQueryFilter = () => {
    if (query.query_filter === '') {
      return queryFilterPlaceholder;
    }

    return (
      <>
        <Expand className={styles.queryFilterExpand} rowHeight={20}>
          <QueryFilter queryFilter={query.query_filter} />
        </Expand>
        <ExpandButton />
        {isCompact ? null : <div className={styles.divider} />}
      </>
    );
  };

  const renderQueryInfo = () => {
    const delimiter = ' • ';
    const dateRange = `${localizeAndFormatTimestamp(query.date_range.start)} - ${localizeAndFormatTimestamp(
      query.date_range.end
    )}`;
    const additionalQueryInfo = [
      `${localizeAndFormatTimestamp(query.date_range.start)} - ${localizeAndFormatTimestamp(query.date_range.end)}`,
    ];

    if (intervalCopy !== '') {
      additionalQueryInfo.unshift(intervalCopy);
    }

    if (query.top_n.length > 0) {
      additionalQueryInfo.push(`Top N: ${query.top_n.join(', ')}`);
    }

    return (
      <OverflowTooltip className={styles.additionalInfo} tooltipContent={getOverflowTooltipContent(dateRange)}>
        {additionalQueryInfo.join(delimiter)}
      </OverflowTooltip>
    );
  };

  return (
    <div className={styles.cardBody}>
      {renderQueryFilter()}
      {renderQueryInfo()}
    </div>
  );
};

```

### `src/components/common/QueryFilter.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';
import hljs from 'highlight.js';

import 'highlight.js/styles/atelier-cave-light.css';
import { querySearchContext } from '../query_view/QuerySearchContext';
import { splitStringIncludingMatches, highlightMatchedText } from '../../utils/StringUtils';

interface QueryFilterProps {
  queryFilter: string;
  className?: string;
  codeClassName?: string;
  ref?: React.RefObject<HTMLPreElement>;
}

const QueryFilter = React.forwardRef(
  ({ queryFilter, className, codeClassName }: QueryFilterProps, ref: React.Ref<HTMLPreElement>) => {
    const codeRef = React.useRef<HTMLElement>(null);

    const searchQuery = React.useContext(querySearchContext);

    const queryTokens = splitStringIncludingMatches(queryFilter, searchQuery.query, searchQuery.regex);
    const highlightSearchQuery = queryTokens.find((el) => el.matched) !== undefined;

    React.useEffect(() => {
      const codeElement = codeRef.current;
      if (highlightSearchQuery) {
        // skip syntax highlighting if highlighting a search query
        return;
      }
      if (codeElement) hljs.highlightBlock(codeElement);
    }, [searchQuery, codeRef, queryFilter]);

    return (
      <pre ref={ref} className={className}>
        {highlightSearchQuery ? (
          <code className={classNames(codeClassName, 'python')} ref={codeRef}>
            {highlightMatchedText(queryTokens)}
          </code>
        ) : (
          <code
            className={classNames(codeClassName, 'python')}
            dangerouslySetInnerHTML={{ __html: hljs.highlight('python', queryFilter, true).value }}
          />
        )}
      </pre>
    );
  }
);
export default QueryFilter;

```

### `src/components/common/SourcesLink.tsx`

```typescript
import * as React from 'react';
import { GithubOutlined } from '@ant-design/icons';

import { parsePathString, getSourcesUrl } from '../../utils/SourceUtils';

interface SourcesLinkProps {
  path: string;
}
export default function SourcesLink({ path }: SourcesLinkProps) {
  const pathInfo = parsePathString(path);
  if (pathInfo == null) {
    // eslint-disable-next-line no-console
    console.warn(`Tried to render SourcesLink for invalid path: ${path}`);
    return <>{path}</>;
  }

  return (
    <>
      {/* eslint-disable-next-line */}
      <a href={getSourcesUrl(pathInfo)} target="_blank" rel="noopener noreferrer">
        <GithubOutlined /> {pathInfo.path}:{pathInfo.lineNumber}
      </a>
      {pathInfo.rest}
    </>
  );
}

```

### `src/components/common/UserSelect.tsx`

```typescript
import * as React from 'react';
import { Select } from 'antd';
import { SelectValue } from 'antd/lib/select';

interface UserSelectProps {
  onSelect: (email: string) => void;
  userResolver: () => Promise<string[]>;
}

const UserSelect = ({ onSelect, userResolver }: UserSelectProps) => {
  const [userOptions, setUserOptions] = React.useState<Array<{ value: string }>>([]);

  React.useEffect(() => {
    async function getUsers() {
      const fetchedUsers = await userResolver();
      setUserOptions(fetchedUsers.map((user) => ({ value: user })));
    }

    getUsers();
  }, [userResolver]);

  const handleSelectUser = (value: SelectValue) => {
    if (typeof value !== 'string') return;
    onSelect(value);
  };

  return (
    <Select
      showSearch
      allowClear
      onClear={() => onSelect('')}
      onChange={handleSelectUser}
      placeholder="Filter by user"
      style={{ width: 200 }}
      options={userOptions}
      filterOption={(input, option) => option?.value.startsWith(input) ?? false}
    />
  );
};

export default UserSelect;

```

### `src/components/docs/UdfDocsView.module.css`

```css
.viewContainer {
  width: 100%;
  max-width: 1300px;
  margin: 0 auto;
}

.udfDocsContainer {
  max-height: 100%;
  background-color: var(--background-primary);
  border-left: 1px solid var(--divider);
  border-right: 1px solid var(--divider);
  padding: 16px;
}

.udfCategoryName {
  margin-bottom: 16px;
}

.udfCategoryContainer {
  margin-bottom: 40px;
}

.udfDetails {
  margin-bottom: 32px;
  padding-right: 128px;
}

.udfDetails > * {
  margin-top: 8px;
}

.udfParamName {
  border-radius: 4px;
  background-color: var(--background-secondary-alt);
  padding: 0 4px;
}

.methodSignatureHighlightedWrap {
  overflow-wrap: break-word;
}

.methodSignatureDisplayArea {
  white-space: pre-wrap;
  background-color: var(--background-secondary-alt);
  border-radius: 8px;
  padding: 8px 80px 8px 8px;
}

```

### `src/components/docs/UdfDocsView.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';
import hljs from 'highlight.js';

import { getUdfDocs } from '../../actions/DocActions';
import usePromiseResult from '../../hooks/usePromiseResult';
import { UdfArgumentSpec, UdfCategory, UdfMethodSpec } from '../../types/DocTypes';
import Text, { TextSizes } from '../../uikit/Text';
import { renderFromPromiseResult } from '../../utils/PromiseResultUtils';

import styles from './UdfDocsView.module.css';

/*
TODO:
- Set up page for other non-UDF documentation (eg have UDF header, probably change URL to be just `/docs`)
- Ability to link to individual function's position on page, have hover button on each UDF title that navigates to
    the UDF's URL
- TOC at side
- Render markdown (or at least simple subsets?) in the docs
 */

interface UdfDocProps {
  udf: UdfMethodSpec;
}

const UdfDoc = ({ udf }: UdfDocProps) => {
  const argumentAsParam = (arg: UdfArgumentSpec): string => {
    const defaultPart = arg.default != null ? ` = ${arg.default}` : '';
    return `${arg.name}: ${arg.type}${defaultPart}`;
  };

  const params = udf.argument_specs.map(argumentAsParam).join(', ');
  const hasAnyArgDocs = udf.argument_specs.some((spec) => spec.doc != null);

  const mainDoc = udf.doc != null && <Text size={TextSizes.LARGE}>{udf.doc}</Text>;
  const argDocs = udf.argument_specs.map(
    (spec) =>
      spec.doc != null && (
        <Text size={TextSizes.LARGE} key={spec.name}>
          <code className={styles.udfParamName}>{spec.name}</code>: {spec.doc}
        </Text>
      )
  );
  const argDocsTitle = hasAnyArgDocs && <Text size={TextSizes.H5}>Parameters</Text>;
  const noDocsNotice = udf.doc == null && !hasAnyArgDocs && <Text size={TextSizes.LARGE}>No documentation yet!</Text>;

  // We need to add the `def` prefix and `: ...` suffix to ensure highlight.js recognizes this as a function
  // declaration, but we don't actually want to display them, so we remove them from the processed HTML.
  const methodSignature = hljs.highlight('python', `def ${udf.name}(${params}) -> ${udf.return_type}: ...`, true);
  const methodSignatureRawHtml = methodSignature.value
    .replace('<span class="hljs-keyword">def</span> ', '')
    .replace(':</span> ...', '</span>');

  return (
    <>
      <Text size={TextSizes.LARGE}>
        <pre className={styles.methodSignatureDisplayArea}>
          <code
            className={classNames(styles.methodSignatureHighlightedWrap, 'python')}
            dangerouslySetInnerHTML={{ __html: methodSignatureRawHtml }}
          />
        </pre>
      </Text>
      <div className={styles.udfDetails}>
        {mainDoc}
        {argDocsTitle}
        {argDocs}
        {noDocsNotice}
      </div>
    </>
  );
};

const renderUdfCategory = (category: UdfCategory) => {
  const categoryName = category.name || 'Other';
  return (
    <div className={styles.udfCategoryContainer} id={categoryName}>
      <Text size={TextSizes.H4} className={styles.udfCategoryName} key={`category-${categoryName}`}>
        {categoryName}
      </Text>
      {category.udfs.map((udf: UdfMethodSpec) => (
        <UdfDoc key={udf.name} udf={udf} />
      ))}
    </div>
  );
};

const UdfDocsView = () => {
  const udfDocsResult = usePromiseResult(getUdfDocs);

  return renderFromPromiseResult(udfDocsResult, (udfDocs) => (
    <div className={styles.viewContainer}>
      <div className={styles.udfDocsContainer}>{udfDocs.map(renderUdfCategory)}</div>
    </div>
  ));
};

export default UdfDocsView;

```

### `src/components/entities/EntityFeatureFilters.module.css`

```css
.inlineFilter {
  margin-right: 8px;
}

.featureFiltersContainer {
  display: flex;
  flex-wrap: nowrap;
  background-color: var(--background-secondary);
  align-items: center;
  flex: 1 1 auto;
  overflow: hidden;
  white-space: nowrap;
}

.divider {
  height: 12px;
  width: 2px;
  background-color: var(--text-light-headings-secondary);
  margin: 0 16px;
}

.closeCircleIcon {
  margin-left: 4px;
}

.featureFilters {
  display: flex;
  flex-wrap: nowrap;
  overflow: hidden;
  flex: 1 1 auto;
}

.featureFilterMenu {
  height: 20px;
  border-radius: 8px;
  padding: 2px 8px;
  font-size: 12px;
  border: 2px solid var(--divider);
  background-color: var(--background-primary);
  display: flex;
  align-items: center;
  cursor: pointer;
}

.menuArrow {
  transform: rotate(90deg);
  margin-left: 2px;
}

.dropdownMenu {
  padding: 16px;
}

.menuFeatureFilter {
  margin-bottom: 16px;
}

.menuFeatureFilter:last-child {
  margin-bottom: 0;
}

```

### `src/components/entities/EntityFeatureFilters.tsx`

```typescript
import * as React from 'react';
import { ResizeObserverEntry } from '@juggle/resize-observer';
import { Spin } from 'antd';
import { debounce, findIndex } from 'lodash';

import { getEventCountsByFeatureForEntityQuery } from '../../actions/EntityActions';
import usePromiseResult from '../../hooks/usePromiseResult';
import useResizeObserver from '../../hooks/useResizeObserver';
import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import useEntityStore from '../../stores/EntityStore';
import useQueryStore from '../../stores/QueryStore';
import DropdownMenu, { MenuOption } from '../../uikit/DropdownMenu';
import Text, { TextColors, TextSizes, TextWeights } from '../../uikit/Text';
import ArrowIcon from '../../uikit/icons/ArrowIcon';
import { Placements } from '../../utils/DOMUtils';
import { renderFromPromiseResult } from '../../utils/PromiseResultUtils';
import { pluralize } from '../../utils/StringUtils';
import FeatureName from '../common/FeatureName';
import FilterPill from '../common/FilterPill';

import styles from './EntityFeatureFilters.module.css';

const DROPDOWN_MENU_WIDTH_WITH_MARGIN = 70;

const Divider = () => <div className={styles.divider} />;

function sortFeatureFiltersByEventVolume([_nameA, countA]: [string, number], [_nameB, countB]: [string, number]) {
  return countB - countA;
}

const debouncedWidthCheck = (setHiddenFilterIndex: Function, setPreviousWidth: Function) =>
  debounce(() => {
    setHiddenFilterIndex(-1);
    setPreviousWidth(window.innerWidth);
  }, 100)();

const EntityFeatureFilters = () => {
  const entityFeatureFilters = useQueryStore((state) => state.entityFeatureFilters);
  const updateEntityFeatureFilters = useQueryStore((state) => state.updateEntityFeatureFilters);

  const eventCountByFeature = useEntityStore((state) => state.eventCountByFeature);
  const totalEventCount = useEntityStore((state) => state.totalEventCount);

  const [hiddenFilterIndex, setHiddenFilterIndex] = React.useState(-1);
  const [previousWidth, setPreviousWidth] = React.useState(window.innerWidth);

  const [containerElement, setContainerElement] = React.useState<HTMLElement | null>(null);

  const contentRef = React.useCallback((node: HTMLElement | null) => {
    if (node != null) {
      setContainerElement(node);
    }
  }, []);

  const handleResize = React.useCallback(
    (entry: ResizeObserverEntry) => {
      // If window is growing, render all of the filters once so we can
      // measure how many should be in the dropdownMenu.
      if (previousWidth < window.innerWidth) {
        debouncedWidthCheck(setHiddenFilterIndex, setPreviousWidth);
        return;
      }

      const index = findIndex(
        entry.target.children,
        (node) => node.getBoundingClientRect().right + DROPDOWN_MENU_WIDTH_WITH_MARGIN >= window.innerWidth
      );

      if (index !== -1 && index !== hiddenFilterIndex) {
        setHiddenFilterIndex(index);
      }

      setPreviousWidth(window.innerWidth);
    },
    [previousWidth, hiddenFilterIndex, setPreviousWidth, setHiddenFilterIndex]
  );

  useResizeObserver(containerElement, handleResize);

  const handleFeatureClick = (featureName: string) => {
    const updatedEntityFeatureFilters = new Set([...entityFeatureFilters]);

    if (updatedEntityFeatureFilters.has(featureName)) {
      updatedEntityFeatureFilters.delete(featureName);
    } else {
      updatedEntityFeatureFilters.add(featureName);
    }

    updateEntityFeatureFilters(updatedEntityFeatureFilters);
  };

  const renderFeatureFilter = ([featureName, count]: [string, number], className: string) => (
    <FilterPill
      onClick={handleFeatureClick}
      filterName={featureName}
      count={count}
      key={featureName}
      isSelected={entityFeatureFilters.has(featureName)}
      className={className}
    />
  );

  const renderFeatureFilters = () => {
    const sortedFeatureNamesToCounts = Object.entries(eventCountByFeature)
      .filter(([_, count]) => count > 0)
      .sort(sortFeatureFiltersByEventVolume);

    // Filters that are past the hiddenFilterIndex are off screen
    // and should be placed in the dropdown menu.
    let filtersToShow = sortedFeatureNamesToCounts;
    let filtersToHide: Array<[string, number]> = [];

    if (hiddenFilterIndex > -1) {
      filtersToShow = sortedFeatureNamesToCounts.slice(0, hiddenFilterIndex);
      filtersToHide = sortedFeatureNamesToCounts.slice(hiddenFilterIndex);
    }

    const featureFilters = filtersToShow.map((val) => renderFeatureFilter(val, styles.inlineFilter));

    if (filtersToHide.length > 0) {
      const dropdownMenuOptions = filtersToHide.map(([featureName, count]) => ({
        label: FeatureName,
        data: { featureName, count },
      }));

      featureFilters.push(
        <DropdownMenu<{ featureName: string; count: number }>
          className={styles.dropdownMenu}
          placement={Placements.BOTTOM_RIGHT}
          key="dropdown"
          renderOption={(option: MenuOption<{ featureName: string; count: number }>) =>
            renderFeatureFilter([option.data.featureName, option.data.count], styles.menuFeatureFilter)
          }
          // @ts-expect-error react-18-upgrade
          options={dropdownMenuOptions}
        >
          <Text
            className={styles.featureFilterMenu}
            size={TextSizes.SMALL}
            weight={TextWeights.SEMIBOLD}
            color={TextColors.LIGHT_HEADINGS_SECONDARY}
          >
            More
            <ArrowIcon width={12} className={styles.menuArrow} />
          </Text>
        </DropdownMenu>
      );
    }

    return featureFilters;
  };

  return (
    <Text
      size={TextSizes.SMALL}
      weight={TextWeights.SEMIBOLD}
      color={TextColors.LIGHT_HEADINGS_SECONDARY}
      className={styles.featureFiltersContainer}
    >
      <Divider />
      {`${totalEventCount.toLocaleString()} ${pluralize('event', totalEventCount)}`}
      <Divider />
      <div className={styles.inlineFilter}>FILTER:</div>
      <div ref={contentRef} className={styles.featureFilters}>
        {renderFeatureFilters()}
      </div>
    </Text>
  );
};

interface EntityFeatureFiltersWrapperProps {
  entityType: string;
}

const EntityFeatureFiltersWrapper = ({ entityType }: EntityFeatureFiltersWrapperProps) => {
  const entityToFeatureSetMapping = useApplicationConfigStore((state) => state.entityToFeatureSetMapping);
  const executedQuery = useQueryStore((state) => state.executedQuery);

  const entityFeatureSet = React.useMemo(() => {
    return entityType == null ? [] : [...(entityToFeatureSetMapping.get(entityType) ?? [])];
  }, [entityToFeatureSetMapping, entityType]);

  const eventCountByFeatureResults = usePromiseResult(
    () => getEventCountsByFeatureForEntityQuery(executedQuery, [...entityFeatureSet]),
    [executedQuery, entityType]
  );

  return renderFromPromiseResult(eventCountByFeatureResults, () => <EntityFeatureFilters />, {
    renderResolving: () => <Spin style={{ margin: '0 auto' }} size="small" />,
  });
};

export default EntityFeatureFiltersWrapper;

```

### `src/components/entities/EntityNameWithPopover.tsx`

```typescript
import { FeatureLocation } from '../../types/ConfigTypes';
import Tooltip, { TooltipSizes } from '../../uikit/Tooltip';
import FeatureName from '../common/FeatureName';

import styles from './EntityNameWithPopover.module.scss';

interface EntityNameWithPopoverProps {
  location: FeatureLocation | undefined;
  name: string;
}

const EntityNameWithPopover = ({ location, name }: EntityNameWithPopoverProps) => {
  const renderContent = () => {
    if (location) {
      return (
        <div className={styles.content}>
          <div className={styles.title}>
            <span className={styles.name}>{location.name}</span>
            <span className={styles.origin}>
              {location.source_path}:{location.source_line}
            </span>
          </div>
          <div className={styles.snippet}>{location.source_snippet}</div>
        </div>
      );
    } else {
      return (
        <div className={styles.content}>
          <div className={styles.title}>{name}</div>
          <div>Could not fetch feature locations. Do you have access to CanViewDocs ACL ability?</div>
        </div>
      );
    }
  };

  return (
    <div className={styles.root}>
      <FeatureName featureName={name} />
      <Tooltip content={renderContent()} size={TooltipSizes.SMALL}>
        <div>
          <span className={styles.trigger}>ⓘ</span>
        </div>
      </Tooltip>
    </div>
  );
};

export default EntityNameWithPopover;

```

### `src/components/entities/EntityPanel.module.css`

```css
.entityPanel {
  width: 100%;
  border-top: 1px solid var(--divider);
  position: relative;
  z-index: 2;
  overflow-y: auto;
}

.entityPanel :global(.ant-collapse) {
  background-color: transparent !important;
}

```

### `src/components/entities/EntityPanel.tsx`

```typescript
import * as React from 'react';
import { useParams } from 'react-router-dom';

import { getLabelsForEntity } from '../../actions/EntityActions';
import usePromiseResult, { PromiseResult } from '../../hooks/usePromiseResult';
import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import useEntityStore, { EntityViewParams } from '../../stores/EntityStore';
import { Label } from '../../types/LabelTypes';
import { sortLabels } from '../../utils/EntityUtils';
import { renderFromPromiseResult } from '../../utils/PromiseResultUtils';
import LabelOverview from './LabelOverview';

import styles from './EntityPanel.module.css';

const EntityPanel = ({ entityType, entityId }: EntityViewParams) => {
  const labelInfoMapping = useApplicationConfigStore((state) => state.labelInfoMapping);
  const [labels, setLabels] = React.useState<Label[]>([]);

  const [selectedEntity, updateSelectedEntity] = useEntityStore((state) => [
    state.selectedEntity,
    state.updateSelectedEntity,
  ]);

  const entityLabelResults: PromiseResult<void> = usePromiseResult(async () => {
    const entityLabels = await getLabelsForEntity(entityId, entityType);
    setLabels(entityLabels);
  }, [entityId, entityType]);

  const handleEntityUpdate = (updatedLabels: Label[]) => {
    setLabels(updatedLabels);

    // If our selected entity is the same as our entity view, reset it so it will refetch
    // labels if reselected.
    if (selectedEntity != null && selectedEntity.type === entityType && selectedEntity.id === entityId) {
      updateSelectedEntity(null);
    }
  };

  return (
    <div className={styles.entityPanel}>
      {renderFromPromiseResult(entityLabelResults, () => {
        const entity = {
          type: entityType,
          id: entityId,
          labels: sortLabels(labels, labelInfoMapping),
          hasLabels: labels.length > 0,
        };
        return <LabelOverview entity={entity} onEntityUpdate={handleEntityUpdate} />;
      })}
    </div>
  );
};

const EntityPanelContainer: React.FC = () => {
  const { entityType, entityId } = useParams<{ entityType: string; entityId: string }>();
  const featureNameToEntityTypeMapping = useApplicationConfigStore((state) => state.featureNameToEntityTypeMapping);
  const isValidEntityRoute = new Set(featureNameToEntityTypeMapping.values()).has(entityType) && entityId != null;

  if (!isValidEntityRoute) return null;

  return <EntityPanel entityType={decodeURIComponent(entityType)} entityId={decodeURIComponent(entityId)} />;
};

export default EntityPanelContainer;

```

### `src/components/entities/EntityViewBar.module.css`

```css
.entityViewBar {
  height: 40px;
  display: flex;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 2px solid var(--divider);
}

.entityType {
  margin-right: 4px;
}

.entityId {
  margin-right: 4px;
}

```

### `src/components/entities/EntityViewBar.tsx`

```typescript
import * as React from 'react';
import { useParams } from 'react-router-dom';

import { EntityViewParams } from '../../stores/EntityStore';
import Text, { TextColors, TextSizes, TextWeights } from '../../uikit/Text';
import BrandDot from '../../uikit/icons/BrandDot';

import styles from './EntityViewBar.module.css';

const EntityViewBar = () => {
  const { entityType, entityId } = useParams<EntityViewParams>();

  return (
    <div className={styles.entityViewBar}>
      <Text
        className={styles.entityType}
        size={TextSizes.LARGE}
        color={TextColors.LIGHT_HEADINGS_SECONDARY}
        weight={TextWeights.LIGHT}
      >
        {decodeURIComponent(entityType)}
      </Text>
      <Text
        className={styles.entityId}
        size={TextSizes.LARGE}
        color={TextColors.LIGHT_HEADINGS_PRIMARY}
        weight={TextWeights.BOLD}
      >
        {decodeURIComponent(entityId)}
      </Text>
      <BrandDot />
    </div>
  );
};

export default EntityViewBar;

```

### `src/components/entities/EntityWithPopover.module.css`

```css
.popoverContent {
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.popoverTitleWrapper {
  max-width: 100%;
  align-self: flex-start;
  padding: 16px;
}

.entityInfo {
  color: var(--text-light-primary);
  overflow-wrap: break-word;
}

.entityId {
  font-weight: 600;
  user-select: text;
}

.routeEntityId {
  color: var(--brand-primary);
}

.routeEntityId:hover {
  color: var(--brand-dark);
}

.entityIdWrapper {
  display: flex;
  align-items: center;
}

.tooltip {
  width: 350px;
  padding: 0;
}

.tooltipOrigin {
  max-width: 100%;
}

.labelPopover {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.labelSectionsContainer {
  overflow-y: auto;
  max-height: 250px;
}

.labelContainer {
  padding: 0 16px;
}

.labelTag {
  margin-top: 8px;
  margin-right: 8px;
}

.popoverInfo {
  background-color: var(--background-secondary-alt);
  color: var(--text-light-secondary);
  width: 100%;
  padding: 8px 16px;
  font-weight: 600;
  border-top: 1px solid var(--divider);
}

.buttonsContainer {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  padding: 16px;
  border-top: 1px solid var(--divider);
}

.clickInfoPoint {
  margin-top: 4px;
}

```

### `src/components/entities/EntityWithPopover.tsx`

```typescript
import * as React from 'react';
import { Empty } from 'antd';
import classNames from 'classnames';
import { useParams } from 'react-router-dom';

import { getLabelsForEntity } from '../../actions/EntityActions';
import usePromiseResult from '../../hooks/usePromiseResult';
import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import useEntityStore from '../../stores/EntityStore';
import { Label, LabelConnotations } from '../../types/LabelTypes';
import OspreyButton, { ButtonColors } from '../../uikit/OspreyButton';
import Text, { TextSizes } from '../../uikit/Text';
import Tooltip from '../../uikit/Tooltip';
import { sortLabels } from '../../utils/EntityUtils';
import { sortLabelsChronologically } from '../../utils/LabelUtils';
import { renderFromPromiseResult } from '../../utils/PromiseResultUtils';
import ExternalLinkButton from '../common/ExternalLinkButton';
import Feature from '../common/Feature';
import LabelTag from '../common/LabelTag';
import LabelSection from './LabelSection';

import styles from './EntityWithPopover.module.css';

const clickInfo = (
  <>
    <div>⌘/◇ + click to add this entity to current query</div>
    <div className={styles.clickInfoPoint}>⌘/◇ + ⇧ + click to query this entity in new tab</div>
  </>
);

interface PopoverContentProps {
  entityId: string;
  entityType: string;
  onEdit: () => void;
}

const PopoverContent = ({ entityId, entityType, onEdit }: PopoverContentProps) => {
  const [selectedEntity, updateSelectedEntity] = useEntityStore((state) => [
    state.selectedEntity,
    state.updateSelectedEntity,
  ]);
  const labelInfoMapping = useApplicationConfigStore((state) => state.labelInfoMapping);
  const selectedEntityFetchResult = usePromiseResult(async () => {
    if (selectedEntity?.type === entityType && selectedEntity?.id === entityId) return;

    const labels = await getLabelsForEntity(entityId, entityType);
    const hasLabels = labels.length > 0;

    updateSelectedEntity({
      type: entityType,
      id: entityId,
      labels: sortLabels(labels, labelInfoMapping),
      hasLabels,
    });
  });

  const renderLabelSections = () => {
    if (!selectedEntity?.hasLabels) return <Empty />;

    return LabelConnotations.map((connotation) => {
      const labels = sortLabelsChronologically(selectedEntity.labels?.[connotation]);
      if (labels.length === 0) return null;

      return (
        <LabelSection key={connotation} connotation={connotation}>
          <div className={styles.labelContainer}>
            {labels.map((label: Label) => (
              <LabelTag className={styles.labelTag} key={label.name} label={label} connotation={connotation} />
            ))}
          </div>
        </LabelSection>
      );
    });
  };

  return (
    <div className={styles.labelPopover}>
      {renderFromPromiseResult(selectedEntityFetchResult, () => (
        <div className={styles.labelSectionsContainer}>{renderLabelSections()}</div>
      ))}
      <div className={styles.popoverInfo}>{clickInfo}</div>
      <div className={styles.buttonsContainer}>
        <OspreyButton color={ButtonColors.DARK_BLUE} style={{ marginRight: 6 }} onClick={onEdit}>
          Edit Labels
        </OspreyButton>
        <ExternalLinkButton entityType={entityType} entityId={entityId} />
      </div>
    </div>
  );
};

interface EntityWithPopoverProps {
  featureName: string;
  entityId: string;
  entityType: string;
}

const EntityWithPopover = ({ entityId, featureName, entityType }: EntityWithPopoverProps) => {
  const updateShowLabelDrawer = useEntityStore((state) => state.updateShowLabelDrawer);
  const { entityType: entityRouteType, entityId: entityRouteId } = useParams<{
    entityType: string;
    entityId: string;
  }>();

  const isRouteEntity = entityRouteType === entityType && entityRouteId === entityId;
  const decodedEntityType = decodeURIComponent(entityType);
  const decodedEntityId = decodeURIComponent(entityId);

  const handleShowLabelDrawer = () => {
    updateShowLabelDrawer(true);
  };

  const isPopoverDisabled = (e: React.MouseEvent<HTMLElement>) => {
    return e.shiftKey;
  };

  const renderPopoverContent = () => (
    <div className={styles.popoverContent}>
      <div className={styles.popoverTitleWrapper}>
        <div className={styles.entityInfo}>
          {decodedEntityType}: {decodedEntityId}
        </div>
        <Text size={TextSizes.H5}>Labels</Text>
      </div>
      <PopoverContent entityId={decodedEntityId} entityType={decodedEntityType} onEdit={handleShowLabelDrawer} />
    </div>
  );

  const renderPopoverOrFeature = () => {
    return (
      <>
        <Tooltip
          className={styles.tooltip}
          contentClassName={styles.tooltipOrigin}
          content={renderPopoverContent()}
          isDisabled={isPopoverDisabled}
        >
          <Feature
            className={classNames(styles.entityId, { [styles.routeEntityId]: isRouteEntity })}
            featureName={featureName}
            value={decodedEntityId}
            onClick={handleShowLabelDrawer}
            isEntity
          />
        </Tooltip>
        <ExternalLinkButton entityType={decodedEntityType} entityId={decodedEntityId} icon />
      </>
    );
  };

  return <div className={styles.entityIdWrapper}>{renderPopoverOrFeature()}</div>;
};

export default EntityWithPopover;

```

### `src/components/entities/FeatureFiltersDetailBar.module.css`

```css
.detailBar {
  width: 100%;
  background-color: var(--link-light-hover);
  transition: 0.2s ease all;
  display: flex;
  align-items: center;
  overflow: hidden;
}

.detailBarShown {
  composes: detailBar;
  padding: 2px 16px;
  border-bottom: 2px solid var(--divider);
  height: 24px;
}

.detailBarHidden {
  composes: detailBar;
  height: 0;
  border-bottom: 0;
}

.filtersApplied {
  margin-right: 8px;
}

.clearFilterButton {
  font-size: 12px;
  margin-left: 4px;
}

```

### `src/components/entities/FeatureFiltersDetailBar.tsx`

```typescript
import * as React from 'react';

import useEntityStore from '../../stores/EntityStore';
import useQueryStore from '../../stores/QueryStore';
import OspreyButton, { ButtonColors } from '../../uikit/OspreyButton';
import Text, { TextColors, TextSizes, TextWeights } from '../../uikit/Text';
import { pluralize } from '../../utils/StringUtils';

import styles from './FeatureFiltersDetailBar.module.css';

const FeatureFiltersDetailBar = () => {
  const entityFeatureFilters = useQueryStore((state) => state.entityFeatureFilters);
  const updateEntityFeatureFilters = useQueryStore((state) => state.updateEntityFeatureFilters);

  const eventCountByFeature = useEntityStore((state) => state.eventCountByFeature);
  const totalEventCount = useEntityStore((state) => state.totalEventCount);

  const eventsShown = Object.entries(eventCountByFeature).reduce((acc, [featureName, eventCount]) => {
    if (entityFeatureFilters.has(featureName)) {
      acc += eventCount;
    }

    return acc;
  }, 0);

  const handleClearFilters = () => {
    updateEntityFeatureFilters(new Set());
  };

  return (
    <div className={entityFeatureFilters.size === 0 ? styles.detailBarHidden : styles.detailBarShown}>
      <Text
        className={styles.filtersApplied}
        size={TextSizes.SMALL}
        weight={TextWeights.SEMIBOLD}
      >{`${entityFeatureFilters.size.toLocaleString()} ${pluralize(
        'filter',
        entityFeatureFilters.size
      )} applied`}</Text>
      <Text
        size={TextSizes.SMALL}
        weight={TextWeights.SEMIBOLD}
        color={TextColors.LIGHT_SECONDARY}
      >{`${eventsShown.toLocaleString()} ${pluralize(
        'event',
        eventsShown
      )} of ${totalEventCount.toLocaleString()}`}</Text>
      <OspreyButton onClick={handleClearFilters} color={ButtonColors.LINK_BRAND} className={styles.clearFilterButton}>
        Clear Filters
      </OspreyButton>
    </div>
  );
};

export default FeatureFiltersDetailBar;

```

### `src/components/entities/LabelDrawer.tsx`

```typescript
import * as React from 'react';
import { Drawer } from 'antd';

import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import useEntityStore from '../../stores/EntityStore';
import { Label } from '../../types/LabelTypes';
import { sortLabels } from '../../utils/EntityUtils';
import LabelOverview from './LabelOverview';

interface LabelDrawerProps {
  childDrawerProps?: {
    isVisible: boolean;
    onDrawerClose: () => void;
  };
}

const LabelDrawer = ({ childDrawerProps }: LabelDrawerProps) => {
  const { selectedEntity, updateSelectedEntity, updateShowLabelDrawer, showLabelDrawer } = useEntityStore();
  const labelInfoMapping = useApplicationConfigStore((state) => state.labelInfoMapping);

  const handleDrawerClose = () => {
    if (childDrawerProps != null) {
      childDrawerProps.onDrawerClose();
    } else {
      updateShowLabelDrawer(false);
    }
  };

  const handleEntityUpdate = (updatedLabels: Label[]) => {
    if (selectedEntity == null) return;

    updateSelectedEntity({
      ...selectedEntity,
      labels: sortLabels(updatedLabels, labelInfoMapping),
      hasLabels: updatedLabels.length > 0,
    });
  };

  const renderDrawerContent = () => {
    if (selectedEntity == null) return <div>No entity selected</div>;

    return <LabelOverview entity={selectedEntity} onEntityUpdate={handleEntityUpdate} onClose={handleDrawerClose} />;
  };

  return (
    <Drawer
      placement="right"
      width={400}
      open={childDrawerProps == null ? showLabelDrawer : childDrawerProps.isVisible}
      onClose={handleDrawerClose}
      closable={false}
      destroyOnClose
    >
      {renderDrawerContent()}
    </Drawer>
  );
};

export default LabelDrawer;

```

### `src/components/entities/LabelOverview.module.css`

```css
.drawerHeader {
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: space-between;
  color: var(--text-light-headings-primary);
}

.entityTypeButtonWrapper {
  width: 100%;
  display: flex;
  justify-content: space-between;
}

.entityId {
  width: 100%;
  overflow-wrap: break-word;
}

.iconButtons {
  display: flex;
  align-items: center;
}

.labelsHeader {
  margin-bottom: 0;
  display: flex;
  flex-direction: row;
  align-items: center;
  word-wrap: anywhere;
}

.successAlert {
  margin: 0 16px 16px;
}

.buttonContainer {
  margin-top: 6px;
  display: flex;
}

.externalLinkButton {
  border-radius: 4px;
}

.addLabelButton {
  border-radius: 4px;
  margin-right: 6px;
}

.emptyLabelList {
  margin: 8px 16px;
}

```

### `src/components/entities/LabelOverview.tsx`

```typescript
import * as React from 'react';
import { Alert } from 'antd';
import { Link } from 'react-router-dom';

import { updateLabelsForEntity } from '../../actions/EntityActions';
import { Entity } from '../../types/EntityTypes';
import {
  LabelConnotations,
  LabelMutation,
  LabelMutationDetails,
  Label,
  LabelConnotation,
} from '../../types/LabelTypes';
import OspreyButton, { ButtonColors } from '../../uikit/OspreyButton';
import Text, { TextColors, TextSizes } from '../../uikit/Text';
import { sortLabelsChronologically } from '../../utils/LabelUtils';
import { makeEntityRoute } from '../../utils/RouteUtils';
import CopyLinkButton from '../common/CopyLinkButton';
import ExternalLinkButton from '../common/ExternalLinkButton';
import LabelForm from '../common/LabelForm';
import LabelRow from './LabelRow';
import LabelSection from './LabelSection';

import { Routes } from '../../Constants';
import styles from './LabelOverview.module.css';

function generateAlertMessage(labelUpdateResult: LabelMutationDetails) {
  const message = [];

  for (const updateType in labelUpdateResult) {
    const labelList = labelUpdateResult[updateType as keyof LabelMutationDetails];
    if (labelList.length > 0) {
      message.push(`Label${labelList.length > 1 ? 's' : ''} ${updateType}: ${labelList.join(', ')}`);
    }
  }

  return message;
}

interface LabelOverviewProps {
  entity: Entity;
  onEntityUpdate: (updatedLabels: Label[]) => void;
  onClose?: () => void;
}

const LabelOverview = ({ entity, onEntityUpdate, onClose }: LabelOverviewProps) => {
  const [showLabelForm, setShowLabelForm] = React.useState(false);
  const [labelUpdateResult, setLabelUpdateResult] = React.useState<LabelMutationDetails | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const entityRoutePath = makeEntityRoute(entity);

  const handleToggleForm = () => {
    setShowLabelForm(!showLabelForm);
    setLabelUpdateResult(null);
  };

  const handleSubmitForm = async (labelMutation: LabelMutation) => {
    setIsSubmitting(true);
    const updates = await updateLabelsForEntity(entity.id, entity.type, [labelMutation]);
    setIsSubmitting(false);

    onEntityUpdate(updates.labels);
    setShowLabelForm(false);
    setLabelUpdateResult(updates.mutation_result);
  };

  const renderLabelForm = () => {
    if (!showLabelForm) return null;
    return (
      <LabelForm
        isSubmitting={isSubmitting}
        entityType={entity.type}
        onSubmit={handleSubmitForm}
        onCancel={handleToggleForm}
      />
    );
  };

  const renderlabelUpdateResultAlert = () => {
    if (labelUpdateResult == null) return null;

    return <Alert className={styles.successAlert} type="success" message={generateAlertMessage(labelUpdateResult)} />;
  };

  const renderEntityViewButton = () => {
    // If there's no onClose, we are not in the drawer, which means we must be in
    // the Entity view already
    if (onClose == null) {
      return (
        <OspreyButton>
          <Link to={Routes.HOME}>Leave Entity View</Link>
        </OspreyButton>
      );
    }
    return (
      <OspreyButton onClick={() => onClose?.()}>
        <Link to={{ pathname: entityRoutePath }}>Go to Entity View</Link>
      </OspreyButton>
    );
  };

  const renderLabelList = (connotation: LabelConnotation) => {
    const labels = sortLabelsChronologically(entity.labels?.[connotation]) ?? [];
    if (labels.length === 0) {
      return (
        <Text size={TextSizes.SMALL} className={styles.emptyLabelList} color={TextColors.LIGHT_SECONDARY}>
          No {connotation} labels.
        </Text>
      );
    }

    return (
      <div>
        {labels.map((label) => (
          <LabelRow
            key={label.name}
            label={label}
            onRemove={handleSubmitForm}
            connotation={connotation}
            isSubmitting={isSubmitting}
          />
        ))}
      </div>
    );
  };

  return (
    <div>
      <div className={styles.drawerHeader}>
        <div className={styles.entityTypeButtonWrapper}>
          <Text size={TextSizes.H5} className={styles.labelsHeader}>
            {entity.type}
          </Text>
          <div className={styles.iconButtons}>
            <CopyLinkButton link={`${document.location.origin}${entityRoutePath}`} />
            <ExternalLinkButton
              className={styles.externalLinkButton}
              entityType={entity.type}
              entityId={entity.id}
              icon
            />
          </div>
        </div>
        <div className={styles.entityId} title={entity.id}>
          {entity.id}
        </div>
        <div className={styles.buttonContainer}>
          <OspreyButton
            color={ButtonColors.DARK_BLUE}
            onClick={handleToggleForm}
            className={styles.addLabelButton}
            size="small"
          >
            Add Label
          </OspreyButton>
          {renderEntityViewButton()}
        </div>
      </div>
      {renderlabelUpdateResultAlert()}
      {renderLabelForm()}
      {LabelConnotations.map((connotation) => (
        <LabelSection key={connotation} connotation={connotation}>
          {renderLabelList(connotation)}
        </LabelSection>
      ))}
    </div>
  );
};

export default LabelOverview;

```

### `src/components/entities/LabelReason.module.css`

```css
.reasonCard {
  margin-bottom: 12px;
  word-wrap: anywhere;
}

.expiresAt {
  margin-top: 4px;
}

```

### `src/components/entities/LabelReason.tsx`

```typescript
import * as React from 'react';

import { LabelReason as Reason } from '../../types/LabelTypes';
import Text, { TextColors, TextSizes, TextWeights } from '../../uikit/Text';
import { isTimestampPast, localizeAndFormatTimestamp } from '../../utils/DateUtils';
import Feature from '../common/Feature';
import RichDescription from './RichDescription';

import styles from './LabelReason.module.css';

const LabelReason = ({ reasonName, reason }: { reasonName: string; reason: Reason }) => {
  const renderReasonExpiry = () => {
    if (reason.expires_at == null) return null;
    const expiryCopy = isTimestampPast(reason.expires_at) ? 'Expired at' : 'Expires at';

    return (
      <Text size={TextSizes.SMALL} color={TextColors.LIGHT_SECONDARY} className={styles.expiresAt}>
        {expiryCopy}: {localizeAndFormatTimestamp(reason.expires_at)}
      </Text>
    );
  };

  return (
    <div className={styles.reasonCard} key={reasonName}>
      {reasonName.startsWith('_') ? (
        <Text weight={TextWeights.SEMIBOLD} color={TextColors.LIGHT_HEADINGS_PRIMARY}>
          {reasonName}
        </Text>
      ) : (
        <Feature value featureName={reasonName} isFeatureNameOnly />
      )}
      <RichDescription description={reason.description} features={reason.features} />
      <Text size={TextSizes.SMALL} color={TextColors.LIGHT_SECONDARY}>
        {localizeAndFormatTimestamp(reason.created_at)}
      </Text>
      {renderReasonExpiry()}
    </div>
  );
};

export default LabelReason;

```

### `src/components/entities/LabelRow.module.css`

```css
.label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 6px 0 28px;
}

.labelInfo {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;
  padding-left: 0;
  text-align: left;
  cursor: pointer;
  width: 100%;
}

.header {
  margin-top: 8px;
}

.labelTag {
  margin-right: 6px;
}

.labelDescription {
  padding: 0 1px 12px 28px;
}

.removeButton {
  opacity: 0;
  transition: 0.2s ease-in-out opacity;
  color: var(--text-light-secondary);
  position: relative;
}

.label:hover .removeButton {
  opacity: 1;
}

.removeButton:hover {
  color: var(--error-primary);
  background-color: transparent;
}

.buttonContainer {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

.iconSidebar {
  position: relative;
  width: 28px;
  height: auto;
}

.iconWrapper {
  position: relative;
  left: -8px;
  width: 32px;
  height: 24px;
  border-radius: 8px;
  border: 1px solid var(--divider);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 4px;
}

.verticalLine {
  width: 1px;
  height: calc(100% - 24px);
  background-color: var(--divider);
  margin-left: 11px;
}

.cancelButton {
  margin-right: 6px;
}

.historyCard {
  display: flex;
}

.historyCardText {
  padding-top: 4px;
}

.content {
  margin-top: 8px;
}

```

### `src/components/entities/LabelRow.tsx`

```typescript
import * as React from 'react';
import { DeleteOutlined } from '@ant-design/icons';

import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import { Label, LabelConnotation, LabelMutation, LabelReason as Reason, LabelStatus } from '../../types/LabelTypes';
import Collapse from '../../uikit/Collapse';
import OspreyButton, { ButtonColors } from '../../uikit/OspreyButton';
import Text, { TextColors, TextSizes } from '../../uikit/Text';
import ManuallyAddedIcon from '../../uikit/icons/ManuallyAddedIcon';
import ManuallyRemovedIcon from '../../uikit/icons/ManuallyRemovedIcon';
import LabelForm from '../common/LabelForm';
import LabelTag from '../common/LabelTag';
import LabelReason from './LabelReason';

import styles from './LabelRow.module.css';

interface LabelRowProps {
  label: Label;
  onRemove: (labelMutation: LabelMutation) => void;
  connotation: LabelConnotation;
  isSubmitting: boolean;
}

export const LabelStatusHistoryMapping: Record<LabelStatus, string> = {
  [LabelStatus.ADDED]: 'AUTOMATICALLY ADDED',
  [LabelStatus.REMOVED]: 'AUTOMATICALLY REMOVED',
  [LabelStatus.MANUALLY_ADDED]: 'MANUALLY ADDED',
  [LabelStatus.MANUALLY_REMOVED]: 'MANUALLY REMOVED',
};

const StatusIcons = {
  [LabelStatus.MANUALLY_ADDED]: <ManuallyAddedIcon width={16} />,
  [LabelStatus.MANUALLY_REMOVED]: <ManuallyRemovedIcon width={16} />,
  [LabelStatus.ADDED]: <ManuallyAddedIcon width={16} />,
  [LabelStatus.REMOVED]: <ManuallyRemovedIcon width={16} />,
};

function sortReasonsChronologically([_a, reasonA]: [string, Reason], [_b, reasonB]: [string, Reason]) {
  return Date.parse(reasonB.created_at) - Date.parse(reasonA.created_at);
}

const LabelRow = ({ label, onRemove, connotation, isSubmitting }: LabelRowProps) => {
  const [isActive, setIsActive] = React.useState(false);
  const [showRemoveForm, setShowRemoveForm] = React.useState(false);
  const labelInfoMapping = useApplicationConfigStore((state) => state.labelInfoMapping);

  const description = labelInfoMapping.get(label.name)?.description;

  const handleDeleteButtonClick = (e: React.SyntheticEvent) => {
    e.stopPropagation();
    if (!isActive) {
      setIsActive(true);
    }

    setShowRemoveForm(!showRemoveForm);
  };

  const header = (
    <div className={styles.label}>
      <div className={styles.labelInfo}>
        <LabelTag className={styles.labelTag} label={label} connotation={connotation} />
      </div>
      {label.status !== LabelStatus.MANUALLY_REMOVED ? (
        <OspreyButton
          className={styles.removeButton}
          color={ButtonColors.LINK_GRAY}
          icon={<DeleteOutlined />}
          onClick={handleDeleteButtonClick}
        />
      ) : null}
    </div>
  );

  const handleRemoveLabel = (labelMutation: LabelMutation) => {
    onRemove(labelMutation);
    setShowRemoveForm(false);
  };

  const renderLabelDescription = () => {
    if (description === null) return null;

    return <div className={styles.labelDescription}>{description}</div>;
  };

  const renderLabelHistory = () => {
    const { reasons, status } = label;
    const labelStateHistory = [{ reasons, status }, ...label.previous_states];

    return labelStateHistory.map((previousState, index) => (
      <div className={styles.historyCard} key={index}>
        <div className={styles.iconSidebar}>
          <div className={styles.iconWrapper}>{StatusIcons[previousState.status]}</div>
          {index === labelStateHistory.length - 1 ? null : <div className={styles.verticalLine} />}
        </div>
        <div className={styles.historyCardText} key={index}>
          <Text size={TextSizes.H7} color={TextColors.LIGHT_SECONDARY}>
            {LabelStatusHistoryMapping[previousState.status]}
          </Text>
          {Object.entries(previousState.reasons)
            .sort(sortReasonsChronologically)
            .map(([reasonName, reason]) => (
              <LabelReason key={reasonName} reasonName={reasonName} reason={reason} />
            ))}
        </div>
      </div>
    ));
  };

  const renderRemoveLabelForm = () => {
    if (!showRemoveForm) return null;

    return (
      <LabelForm
        label={label}
        title={<Text size={TextSizes.H5}>Remove Label</Text>}
        isSubmitting={isSubmitting}
        onCancel={() => setShowRemoveForm(false)}
        onSubmit={handleRemoveLabel}
      />
    );
  };

  return (
    <Collapse
      headerClassName={styles.header}
      header={header}
      isActive={isActive}
      onClick={() => setIsActive(!isActive)}
    >
      <div className={styles.content}>
        {renderRemoveLabelForm()}
        {renderLabelDescription()}
        {renderLabelHistory()}
      </div>
    </Collapse>
  );
};

export default LabelRow;

```

### `src/components/entities/LabelSection.module.css`

```css
.labelSection {
  padding-bottom: 8px;
}

.labelConnotationContainer {
  position: relative;
  padding: 4px 16px;
  width: 100%;
  background-color: var(--background-secondary-alt);
  height: 30px;
  display: flex;
  align-items: center;
}

.labelConnotation {
  text-transform: capitalize;
  color: var(--text-light-headings-primary);
  display: flex;
  align-items: center;
}

.connotationIcon {
  margin-right: 4px;
  display: flex;
}

```

### `src/components/entities/LabelSection.tsx`

```typescript
import * as React from 'react';
import { isEmpty } from 'lodash';

import { LabelConnotation } from '../../types/LabelTypes';
import Text, { TextSizes, TextWeights } from '../../uikit/Text';
import FrownyFaceIcon from '../../uikit/icons/FrownyFaceIcon';
import NeutralFaceIcon from '../../uikit/icons/NeutralFaceIcon';
import SmileyFaceIcon from '../../uikit/icons/SmileyFaceIcon';

import styles from './LabelSection.module.css';

const LabelConnotationIcons = {
  [LabelConnotation.NEGATIVE]: <FrownyFaceIcon />,
  [LabelConnotation.POSITIVE]: <SmileyFaceIcon />,
  [LabelConnotation.NEUTRAL]: <NeutralFaceIcon />,
};

interface LabelSectionProps {
  connotation: LabelConnotation;
  children: React.ReactNode;
}

const LabelSection = ({ connotation, children }: LabelSectionProps) => {
  if (isEmpty(children) || children == null) return null;

  return (
    <div className={styles.labelSection}>
      <div className={styles.labelConnotationContainer}>
        <Text size={TextSizes.SMALL} weight={TextWeights.SEMIBOLD} className={styles.labelConnotation}>
          <span className={styles.connotationIcon}>{LabelConnotationIcons[connotation]}</span>
          {connotation}
        </Text>
      </div>
      {children}
    </div>
  );
};

export default LabelSection;

```

### `src/components/entities/RichDescription.module.css`

```css
.interpolatedFeature {
  font-weight: 600;
}

```

### `src/components/entities/RichDescription.tsx`

```typescript
import * as React from 'react';

import RichDescriptorValue from './RichDescriptorValue';

import styles from './RichDescription.module.css';

interface RichDescriptionProps {
  description: string;
  features: { [featureName: string]: string };
}

const INTERPOLATE_REG_EX = /{([A-z0-9_]+)}/;
const SPLIT_REG_EX = /(:?{[A-z0-9_]+})/;

const RichDescription = ({ description, features }: RichDescriptionProps) => {
  const interpolatedDescription = description.split(SPLIT_REG_EX).map((part, i) => {
    const matchList = part.match(INTERPOLATE_REG_EX);
    const featureName = matchList != null ? matchList[1] : null;
    const featureVal = featureName != null ? features[featureName] : null;

    if (featureName == null || featureVal == null) return part;

    return (
      <span key={i} title={featureName} className={styles.interpolatedFeature}>
        <RichDescriptorValue featureName={featureName} featureVal={featureVal} />
      </span>
    );
  });
  return <div>{interpolatedDescription}</div>;
};

export default RichDescription;

```

### `src/components/entities/RichDescriptorValue.tsx`

```typescript
import * as React from 'react';
import { Link } from 'react-router-dom';

import useApplicationConfigStore from '../../stores/ApplicationConfigStore';

interface RichDescriptorValueProps {
  featureName: string;
  featureVal: string;
}

const RichDescriptorValue = ({ featureName, featureVal }: RichDescriptorValueProps) => {
  const featureNameToEntityTypeMapping = useApplicationConfigStore((state) => state.featureNameToEntityTypeMapping);
  const entityType = featureNameToEntityTypeMapping.get(featureName);

  if (entityType != null) {
    const entityRoutePath = `/entity/${entityType}/${featureVal}`;
    return <Link to={{ pathname: entityRoutePath }}>{featureVal}</Link>;
  }

  return <>{featureVal}</>;
};

export default RichDescriptorValue;

```

### `src/components/event_stream/CustomFeaturesFilter.module.css`

```css
.featureFilter {
  border-radius: 4px;
  background-color: var(--link-light-hover);
  margin-top: 8px;
  margin-bottom: 16px;
}

.arrowIconWrapper {
  left: unset;
  right: 6px;
}

.arrowIconWrapperHidden {
  display: none;
}

.collapseHeader {
  display: flex;
  align-items: center;
  padding: 8px;
  max-height: 32px;
}

.clearFilterButton {
  height: unset;
  font-size: 12px;
  padding: 0 0 0 8px;
}

.contentWrapper {
  display: flex;
  flex-wrap: wrap;
  max-height: 72px;
  overflow: scroll;
  padding: 8px 8px 2px;
}

.contentWrapperActive {
  composes: contentWrapper;
  border-top: 1px solid var(--link-muted);
}

.filterPill {
  margin: 0 4px 6px 0;
}

```

### `src/components/event_stream/CustomFeaturesFilter.tsx`

```typescript
import * as React from 'react';

import Collapse from '../../uikit/Collapse';
import OspreyButton, { ButtonColors, ButtonWeights } from '../../uikit/OspreyButton';
import Text, { TextColors, TextSizes, TextWeights } from '../../uikit/Text';
import { pluralize } from '../../utils/StringUtils';
import FilterPill from '../common/FilterPill';

import styles from './CustomFeaturesFilter.module.css';

interface CustomFeaturesFilterProps {
  selectedCustomFeatures: Set<string>;
  useCustomFeatures: boolean;
  onClearFilters: () => void;
  onRemoveSelectedFeature: (features: Set<string>) => void;
}

const CustomFeaturesFilter = ({
  selectedCustomFeatures,
  useCustomFeatures,
  onClearFilters,
  onRemoveSelectedFeature,
}: CustomFeaturesFilterProps) => {
  const [showHidden, setShowHidden] = React.useState(false);

  const isFilterActive = selectedCustomFeatures.size > 0;

  const removeSelectedFeature = (feature: string) => {
    const updatedFeatures = new Set([...selectedCustomFeatures]);
    updatedFeatures.delete(feature);
    if (updatedFeatures.size === 0) {
      setShowHidden(false);
    }
    onRemoveSelectedFeature(updatedFeatures);
  };

  const clearFilters = (e: React.SyntheticEvent) => {
    e.stopPropagation();
    onClearFilters();
    setShowHidden(false);
  };

  const header = (
    <div className={styles.collapseHeader}>
      <Text size={TextSizes.SMALL} weight={TextWeights.SEMIBOLD} color={TextColors.LIGHT_PRIMARY}>
        {useCustomFeatures
          ? `${selectedCustomFeatures.size.toLocaleString()} ${pluralize(
              'filter',
              selectedCustomFeatures.size
            )} selected`
          : 'The default features shown vary by event type'}
      </Text>
      {isFilterActive ? (
        <OspreyButton
          onClick={clearFilters}
          color={ButtonColors.LINK_BRAND}
          className={styles.clearFilterButton}
          weight={ButtonWeights.BOLD}
        >
          Clear Filters
        </OspreyButton>
      ) : null}
    </div>
  );

  const renderSelectedCustomFeatures = () => {
    return [...selectedCustomFeatures].map((featureName) => (
      <FilterPill
        className={styles.filterPill}
        key={featureName}
        filterName={featureName}
        isSelected
        onClick={() => removeSelectedFeature(featureName)}
      />
    ));
  };

  return (
    <div className={styles.featureFilter}>
      <Collapse
        header={header}
        isActive={showHidden && isFilterActive}
        onClick={isFilterActive ? () => setShowHidden(!showHidden) : () => {}}
        contentClassName={showHidden ? styles.contentWrapperActive : styles.contentWrapper}
        arrowWrapperClassName={isFilterActive ? styles.arrowIconWrapper : styles.arrowIconWrapperHidden}
        defaultArrowPosition={false}
      >
        {renderSelectedCustomFeatures()}
      </Collapse>
    </div>
  );
};

export default CustomFeaturesFilter;

```

### `src/components/event_stream/EventDetailsPanel.module.css`

```css
.panel {
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  max-height: 100vh;
  position: relative;
}

.eventContents {
  padding: 20px;
}

.timestampContainer {
  display: flex;
  align-items: center;
  gap: 6px;
}

.timestamp {
  margin-left: 6px;
}

.eventName {
  text-transform: uppercase;
}

.tableFilters {
  margin-top: 1rem;
  display: flex;
  border: rgba(0, 0, 0, 0.06) 1px solid;
  background-color: var(--background-primary);
}

.filterSearch {
  margin-right: 1rem;
  border: none;
}

.switchContainer {
  display: flex;
  border-left: rgba(0, 0, 0, 0.06) 1px solid;
  padding: 0.5rem 0.5rem 0.5rem 1rem;
}

.switchText {
  display: block;
  width: max-content;
  margin-left: 0.5rem;
}

.jsonWrap {
  overflow-wrap: break-word;
}

.json {
  white-space: pre-wrap;
}

.errorTrace {
  overflow-x: auto;
}

```

### `src/components/event_stream/EventDetailsPanel.tsx`

```typescript
import React, { useState } from 'react';
import {
  ExclamationCircleOutlined,
  AimOutlined,
  ImportOutlined,
  ExportOutlined,
  SearchOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { Menu, List, Input, Switch, Descriptions } from 'antd';
import classNames from 'classnames';
import hljs from 'highlight.js';

import { getDetailedEventFeatures } from '../../actions/EventActions';
import usePromiseResult from '../../hooks/usePromiseResult';
import { StoredExecutionResult } from '../../types/QueryTypes';
import Text, { TextSizes, TextColors } from '../../uikit/Text';
import { formatUtcTimestamp, localizeAndFormatTimestamp } from '../../utils/DateUtils';
import { renderFromPromiseResult } from '../../utils/PromiseResultUtils';
import Feature from '../common/Feature';
import SourcesLink from '../common/SourcesLink';

import styles from './EventDetailsPanel.module.css';
import 'highlight.js/styles/github.css';
import { wrapEntityKeysWithFeatureLocationsMenu } from '../../utils/EntityUtils';
import { FeatureLocation } from '../../types/ConfigTypes';
import Tooltip, { TooltipSizes } from '../../uikit/Tooltip';

enum EventDataTabs {
  EventDetails = 'EVENT_DETAILS',
  ActionData = 'ACTION_DATA',
  ErrorTraces = 'ERROR_TRACES',
  ExtractedFeatures = 'EXTRACTED_FEATURES',
}

interface EventDetailsPanelProps {
  eventId: string;
  featureLocations: FeatureLocation[] | undefined;
}

interface MenuBarProps {
  onClick: (params: { key: React.Key }) => void;
  currentTab: EventDataTabs;
  storedExecutionResult: StoredExecutionResult;
}

const MenuBar = ({ onClick, currentTab, storedExecutionResult }: MenuBarProps) => {
  const numErrorTraces = storedExecutionResult.error_traces.length;
  return (
    <Menu className={styles.__invalid_menu} onClick={onClick} selectedKeys={[currentTab]} mode="horizontal">
      <Menu.Item key={EventDataTabs.EventDetails} icon={<AimOutlined />}>
        Overview
      </Menu.Item>
      {numErrorTraces > 0 ? (
        <Menu.Item key={EventDataTabs.ErrorTraces} icon={<ExclamationCircleOutlined />}>
          <b>{numErrorTraces}</b> Error{numErrorTraces === 1 ? '' : 's'}
        </Menu.Item>
      ) : null}
      <Menu.Item key={EventDataTabs.ActionData} icon={<ImportOutlined />}>
        Input
      </Menu.Item>
      <Menu.Item key={EventDataTabs.ExtractedFeatures} icon={<ExportOutlined />}>
        Output
      </Menu.Item>
    </Menu>
  );
};

const Json = ({ content }: { content: any }) => {
  const code = hljs.highlight('json', JSON.stringify(content, null, 2), true);
  return (
    <pre className={styles.jsonWrap}>
      <code className={classNames(styles.json, 'json')} dangerouslySetInnerHTML={{ __html: code.value }} />
    </pre>
  );
};

interface ClearSearchButtonProps {
  searchValue: string;
  onClearSearchClick: () => void;
}

const ClearSearchButton = ({ searchValue, onClearSearchClick }: ClearSearchButtonProps) => {
  if (searchValue.length > 0) {
    return <CloseCircleOutlined onClick={() => onClearSearchClick()} />;
  }
  return null;
};

interface EventDetailsProps {
  storedExecutionResult: StoredExecutionResult;
  featureLocations: FeatureLocation[] | undefined;
}

const EventDetails = ({ storedExecutionResult, featureLocations }: EventDetailsProps) => {
  const extractedFeatures = storedExecutionResult.extracted_features;
  const [value, setValue] = useState('');
  const [includeNullValues, setIncludeNullValues] = useState(true);

  const shouldDisplayRow = (featureName: string, featureValue: string) => {
    return featureName.toLowerCase().includes(value.toLowerCase()) && (includeNullValues || featureValue !== null);
  };

  return (
    <>
      <div>
        <Text size={TextSizes.H5}>ACTION ID: {storedExecutionResult.id}</Text>
        <Feature
          className={styles.eventName}
          featureName="ActionName"
          value={storedExecutionResult.extracted_features.ActionName}
        />
        <div className={styles.timestampContainer}>
          <Text tag="span" color={TextColors.LIGHT_SECONDARY} size={TextSizes.XSMALL} className={styles.timestamp}>
            {localizeAndFormatTimestamp(storedExecutionResult.timestamp)}
          </Text>
          <Tooltip
            content={
              <Text tag="span" color={TextColors.LIGHT_SECONDARY} className={styles.timestamp}>
                {formatUtcTimestamp(storedExecutionResult.timestamp)}
              </Text>
            }
            size={TooltipSizes.SMALL}
          >
            <span>ⓘ</span>
          </Tooltip>
        </div>
      </div>
      <div className={styles.tableFilters}>
        <Input
          className={styles.filterSearch}
          placeholder="Filter feature list"
          value={value}
          prefix={<SearchOutlined />}
          suffix={<ClearSearchButton searchValue={value} onClearSearchClick={() => setValue('')} />}
          onChange={(e) => setValue(e.target.value)}
        />
        <div className={styles.switchContainer}>
          <Switch checked={!includeNullValues} onClick={() => setIncludeNullValues(!includeNullValues)} />
          <div className={styles.switchText}>Hide empty features</div>
        </div>
      </div>
      <Descriptions size="small" column={1} bordered>
        {Object.entries(extractedFeatures).map(([featureName, featureValue]) => {
          return shouldDisplayRow(featureName, featureValue) ? (
            <Descriptions.Item
              label={wrapEntityKeysWithFeatureLocationsMenu(featureName, featureLocations)}
              key={featureName}
            >
              <Feature featureName={featureName} value={featureValue} textSelectable={featureValue != null} />
            </Descriptions.Item>
          ) : null;
        })}
      </Descriptions>
    </>
  );
};

interface ErrorTracesProps {
  storedExecutionResult: StoredExecutionResult;
}

const ErrorTraces = ({ storedExecutionResult }: ErrorTracesProps): React.ReactElement => {
  return (
    <List
      itemLayout="horizontal"
      dataSource={storedExecutionResult.error_traces}
      renderItem={(trace, idx) => {
        const [path, content] = trace.rules_source_location.split(' - ');

        return (
          <List.Item>
            <List.Item.Meta
              className={styles.errorTrace}
              title={
                <>
                  <b>{`#${idx + 1}: `}</b>
                  <SourcesLink path={path} /> - <code>{content}</code>
                </>
              }
              description={<pre>{trace.traceback}</pre>}
            />
          </List.Item>
        );
      }}
    />
  );
};

interface EventStreamContentProps {
  storedExecutionResult: StoredExecutionResult;
  featureLocations: FeatureLocation[] | undefined;
}

const EventDetailsPanelContent = ({ storedExecutionResult, featureLocations }: EventStreamContentProps) => {
  const [currentTab, setCurrentTab] = React.useState<EventDataTabs>(EventDataTabs.EventDetails);

  const handleMenuClick = React.useCallback((e: { key: React.Key }) => {
    setCurrentTab(e.key as EventDataTabs);
  }, []);

  const renderStreamContent = () => {
    switch (currentTab) {
      case EventDataTabs.EventDetails:
        return <EventDetails storedExecutionResult={storedExecutionResult} featureLocations={featureLocations} />;
      case EventDataTabs.ActionData:
        return <Json content={storedExecutionResult.action_data} />;
      case EventDataTabs.ErrorTraces:
        return <ErrorTraces storedExecutionResult={storedExecutionResult} />;
      case EventDataTabs.ExtractedFeatures:
        return <Json content={storedExecutionResult.extracted_features} />;
    }
  };

  return (
    <>
      <MenuBar currentTab={currentTab} onClick={handleMenuClick} storedExecutionResult={storedExecutionResult} />
      <div className={styles.eventContents}>{renderStreamContent()}</div>
    </>
  );
};

const EventDetailsPanel = ({ eventId, featureLocations }: EventDetailsPanelProps) => {
  const panelContent = renderFromPromiseResult(
    usePromiseResult(() => getDetailedEventFeatures(eventId), [eventId]),
    (storedExecutionResult) => (
      <EventDetailsPanelContent storedExecutionResult={storedExecutionResult} featureLocations={featureLocations} />
    )
  );

  return <div className={styles.panel}>{panelContent}</div>;
};

export default EventDetailsPanel;

```

### `src/components/event_stream/EventPage.tsx`

```typescript
import * as React from 'react';
import { useParams } from 'react-router-dom';

import EventDetailsPanel from './EventDetailsPanel';
import { FeatureLocation } from '../../types/ConfigTypes';
import { getFeatureLocations } from '../../actions/EventActions';

interface Params {
  eventId: string;
}

const EventPage: React.FC = () => {
  const { eventId } = useParams<Params>();
  const [featureLocations, setFeatureLocations] = React.useState<FeatureLocation[] | undefined>([]);

  React.useEffect(() => {
    (async () => {
      const res = await getFeatureLocations();
      setFeatureLocations(res.locations);
    })();
  }, []);

  return <EventDetailsPanel eventId={eventId} featureLocations={featureLocations} />;
};

export default EventPage;

```

### `src/components/event_stream/EventStream.module.css`

```css
.eventStreamPanel {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

.listWrapper {
  position: relative;
  flex-grow: 1;
  display: flex;
}

.eventStreamList {
  width: 100%;
}

.virtualizedList {
  outline: none;
}

.iconText {
  margin-right: 8px;
}

.listItemWrapper {
  padding: 0 16px;
}

.listView:hover {
  background-color: var(--background-secondary);
}

.buttonContainer {
  display: flex;
}

.viewSwitchButton {
  margin-right: 6px;
}

```

### `src/components/event_stream/EventStream.tsx`

```typescript
import * as React from 'react';
import {
  UnorderedListOutlined,
  ProfileOutlined,
  SortAscendingOutlined,
  SortDescendingOutlined,
} from '@ant-design/icons';
import { Empty, List, Skeleton, Tooltip, Spin } from 'antd';
import classNames from 'classnames';
import { memoize } from 'lodash';
import { AutoSizer, List as VList, ListRowProps } from 'react-virtualized';
import shallow from 'zustand/shallow';

import { getFeatureLocations, getScanQueryResults } from '../../actions/EventActions';
import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import useQueryStore from '../../stores/QueryStore';
import { OspreyEvent, ScanQueryOrder } from '../../types/QueryTypes';
import OspreyButton from '../../uikit/OspreyButton';
import EventStreamIcon from '../../uikit/icons/EventStreamIcon';
import Panel from '../common/Panel';
import EventStreamCard from './EventStreamCard';
import FeatureSelectModal from './FeatureSelectModal';

import styles from './EventStream.module.css';
import { FeatureLocation } from '../../types/ConfigTypes';

const QUERY_ROW_LIMIT = 100;
const HEADER_HEIGHT = 44;
const ADDITIONAL_PADDING = 4;
const ROW_HEIGHT = 44;
const EMPTY_ROW_HEIGHT = 116;
const NUM_COLUMNS = 3;

const calculateCardHeight = (currentHeight: number, featureBlock: readonly string[], item: OspreyEvent) => {
  const numFeatures = featureBlock.reduce(
    (acc, feature) => acc + (Object.prototype.hasOwnProperty.call(item.extracted_features, feature) ? 1 : 0),
    0
  );
  const rows = Math.ceil(numFeatures / NUM_COLUMNS);
  return currentHeight + rows * ROW_HEIGHT;
};

const EventStream: React.FC = () => {
  const [
    executedQuery,
    sortOrder,
    entityFeatureFilters,
    applyIfQueryIsCurrent,
    updateSortOrder,
    customSummaryFeatures,
  ] = useQueryStore(
    (state) => [
      state.executedQuery,
      state.sortOrder,
      state.entityFeatureFilters,
      state.applyIfQueryIsCurrent,
      state.updateSortOrder,
      state.customSummaryFeatures,
    ],
    shallow
  );
  const defaultSummaryFeatures = useApplicationConfigStore((state) => state.defaultSummaryFeatures);
  const vlistRef = React.useRef<VList>(null);

  const [isLoading, setIsLoading] = React.useState(false);
  const [eventStream, setEventStream] = React.useState<OspreyEvent[]>([]);
  const [queryOffset, setQueryOffset] = React.useState<string | null>(null);
  const [isListView, setIsListView] = React.useState(false);
  const [featureLocations, setFeatureLocations] = React.useState<FeatureLocation[] | undefined>([]);

  const handleScanQuery = React.useCallback(
    async (currentEvents: OspreyEvent[] = [], newQueryOffset?: string) => {
      setIsLoading(true);
      const { events, offset } = await getScanQueryResults(
        { ...executedQuery, entityFeatureFilters },
        sortOrder,
        QUERY_ROW_LIMIT,
        newQueryOffset
      );

      applyIfQueryIsCurrent(executedQuery, () => {
        setEventStream([...currentEvents, ...events]);
        setQueryOffset(offset);
        setIsLoading(false);
      });
    },
    [executedQuery, sortOrder, entityFeatureFilters, applyIfQueryIsCurrent]
  );

  React.useEffect(() => {
    const { start, end } = executedQuery;
    setEventStream([]);
    setQueryOffset(null);

    if (start !== '' && end !== '') {
      // This should only be called if the query has changed, so reset local state
      handleScanQuery();
    }
  }, [handleScanQuery, executedQuery]);

  React.useEffect(() => {
    (async () => {
      const { locations } = await getFeatureLocations();
      setFeatureLocations(locations);
    })();
  }, []);

  React.useEffect(() => {
    vlistRef.current?.recomputeRowHeights();
  }, [customSummaryFeatures, isListView, vlistRef]);

  const handlePaginatedScanQuery = () => {
    if (eventStream.length === 0 || queryOffset == null || isLoading) return;
    handleScanQuery(eventStream, queryOffset);
  };

  const shouldLoadMoreResults = (index: number): boolean => {
    return eventStream.length - index < 5;
  };

  const getSummaryFeatures = React.useMemo(
    () =>
      memoize((actionName: string) =>
        defaultSummaryFeatures.filter((f) => f.appliesTo(actionName)).map((f) => f.features)
      ),
    [defaultSummaryFeatures]
  );

  const renderListRows = ({ key, index, style, isVisible }: ListRowProps) => {
    if (isVisible && shouldLoadMoreResults(index)) {
      handlePaginatedScanQuery();
    }

    const item = eventStream[index];
    const features =
      customSummaryFeatures == null ? getSummaryFeatures(item.extracted_features.ActionName) : [customSummaryFeatures];

    return (
      <List.Item
        className={classNames(styles.listItemWrapper, { [styles.listView]: isListView })}
        key={key}
        style={style}
      >
        <Skeleton loading={isLoading} active title paragraph={{ rows: 5 }}>
          <EventStreamCard
            selectedFeatures={features}
            featureLocations={featureLocations}
            eventDetails={item}
            isListView={isListView}
          />
        </Skeleton>
      </List.Item>
    );
  };

  const getRowHeight = ({ index }: { index: number }): number => {
    if (isListView) return HEADER_HEIGHT;

    const features =
      customSummaryFeatures == null
        ? getSummaryFeatures(eventStream[index].extracted_features.ActionName)
        : [customSummaryFeatures];

    if (!features.length) {
      return EMPTY_ROW_HEIGHT;
    }

    return features.reduce(
      (height: number, featureBlock: readonly string[]) =>
        calculateCardHeight(height, featureBlock, eventStream[index]),
      HEADER_HEIGHT + ADDITIONAL_PADDING
    );
  };

  const renderVirtualizedList = () => {
    if (eventStream.length === 0) {
      return isLoading ? (
        <Spin size="large" style={{ position: 'absolute', top: 40, left: 0, right: 0 }} />
      ) : (
        <Empty style={{ paddingTop: 40 }} />
      );
    }

    return (
      <AutoSizer>
        {({ width, height }) => (
          <VList
            className={styles.virtualizedList}
            width={width}
            height={height}
            rowCount={eventStream.length}
            rowHeight={getRowHeight}
            rowRenderer={renderListRows}
            ref={vlistRef}
          />
        )}
      </AutoSizer>
    );
  };

  const handleToggleViewType = () => {
    setIsListView(!isListView);
  };

  const handleSetQueryOrder = (order: ScanQueryOrder) => {
    updateSortOrder(order);
  };

  const renderTitleRight = () => {
    const viewSwitchIcon = isListView ? <ProfileOutlined /> : <UnorderedListOutlined />;
    const oppositeView = isListView ? 'card' : 'list';
    const oppositeOrder = sortOrder === ScanQueryOrder.ASCENDING ? ScanQueryOrder.DESCENDING : ScanQueryOrder.ASCENDING;
    const orderIcon = sortOrder === ScanQueryOrder.ASCENDING ? <SortAscendingOutlined /> : <SortDescendingOutlined />;

    return (
      <div className={styles.buttonContainer}>
        <Tooltip title={`Switch to sorting by date ${oppositeOrder} (currently: ${sortOrder})`}>
          <span>
            <OspreyButton
              className={styles.viewSwitchButton}
              icon={orderIcon}
              onClick={() => handleSetQueryOrder(oppositeOrder)}
            />
          </span>
        </Tooltip>
        <Tooltip title={`Switch to ${oppositeView} view`}>
          <span>
            <OspreyButton className={styles.viewSwitchButton} icon={viewSwitchIcon} onClick={handleToggleViewType} />
          </span>
        </Tooltip>
        <FeatureSelectModal />
      </div>
    );
  };

  return (
    <Panel
      className={styles.eventStreamPanel}
      title="Event Stream"
      titleRight={renderTitleRight()}
      icon={<EventStreamIcon />}
    >
      <div className={styles.listWrapper}>
        <div className={styles.eventStreamList}>{renderVirtualizedList()}</div>
      </div>
    </Panel>
  );
};

export default EventStream;

```

### `src/components/event_stream/EventStreamCard.module.css`

```css
.card {
  width: 100%;
}

.description {
  width: 100%;
  height: 100%;
}

.description :global(table) {
  table-layout: fixed !important;
}

.contentTable {
  margin-left: -8px;
}

.cardTitle {
  display: flex;
  align-items: center;
}

.cardHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 6px 0;
}

.actionName {
  text-transform: lowercase;
  font-weight: 600;
}

.timestamp {
  margin: 0 6px;
}

:global(.ant-descriptions-item-label),
:global(.ant-descriptions-item-content) {
  padding: 2px 4px !important;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.eventStreamCard :global(.ant-descriptions):nth-child(n + 2) :global(.ant-descriptions-view) {
  border-top: none !important;
}

```

### `src/components/event_stream/EventStreamCard.tsx`

```typescript
import * as React from 'react';
import { Empty } from 'antd';
import NewWindow from 'react-new-window';
import { useParams } from 'react-router-dom';

import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import { EntityViewParams } from '../../stores/EntityStore';
import { OspreyEvent } from '../../types/QueryTypes';
import OspreyButton from '../../uikit/OspreyButton';
import Text, { TextColors } from '../../uikit/Text';
import { formatUtcTimestamp, localizeAndFormatTimestamp } from '../../utils/DateUtils';
import { wrapEntityKeysWithFeatureLocationsMenu, wrapEntityValuesWithLabelMenu } from '../../utils/EntityUtils';
import CopyLinkButton from '../common/CopyLinkButton';
import Feature from '../common/Feature';
import PropertyTable, { Entries } from '../common/PropertyTable';

import styles from './EventStreamCard.module.css';
import { FeatureLocation } from '../../types/ConfigTypes';
import Tooltip, { TooltipSizes } from '../../uikit/Tooltip';

interface EventStreamCardProps {
  eventDetails: OspreyEvent;
  selectedFeatures: Array<readonly string[]>;
  featureLocations: Array<FeatureLocation> | undefined;
  isListView: boolean;
}

const EventStreamCard = ({ eventDetails, selectedFeatures, featureLocations, isListView }: EventStreamCardProps) => {
  const [showWindow, setShowWindow] = React.useState(false);
  const { entityId, entityType } = useParams<EntityViewParams>();
  const decodedEntityId = entityId != null ? decodeURIComponent(entityId) : null;
  const decodedEntityType = entityType != null ? decodeURIComponent(entityType) : null;
  const featureNameToEntityTypeMapping = useApplicationConfigStore((state) => state.featureNameToEntityTypeMapping);

  const handleShowWindow = () => {
    setShowWindow(true);
  };

  const handleWindowClose = () => {
    setShowWindow(false);
  };

  const renderDescriptionBlock = (features: readonly string[]) => {
    const entries: Record<string, string> = {};

    features.forEach((feature) => {
      if (Object.prototype.hasOwnProperty.call(eventDetails.extracted_features, feature)) {
        entries[feature] = eventDetails.extracted_features[feature];
      }
    });

    if (Object.keys(entries).length === 0) return null;

    return entries;
  };

  const renderContent = () => {
    if (isListView) return null;

    const features = selectedFeatures.map(renderDescriptionBlock).filter((block) => block != null) as Entries[];
    const isEmpty = features.length === 0;
    let entityViewProps = {};

    if (decodedEntityId != null && decodedEntityType != null) {
      entityViewProps = {
        shouldHighlightCell: ([key, value]: [string, string]) => {
          if (value == null) return false;
          const featureEntityType = featureNameToEntityTypeMapping.get(key);
          return decodedEntityType === featureEntityType && decodedEntityId.toString() === value.toString();
        },
      };
    }

    return isEmpty ? (
      <Empty imageStyle={{ height: 40 }} description="No data for selected features" />
    ) : (
      <PropertyTable
        className={styles.contentTable}
        entries={features}
        columns={3}
        renderKey={([key]) => wrapEntityKeysWithFeatureLocationsMenu(key, featureLocations)}
        renderValue={([key, value]) => wrapEntityValuesWithLabelMenu(value, key)}
        {...entityViewProps}
      />
    );
  };

  const eventUrl = `${document.location.origin}/events/${eventDetails.id}`;

  const cardTitle = (
    <div className={styles.cardTitle}>
      <Feature
        className={styles.actionName}
        featureName="ActionName"
        value={eventDetails.extracted_features.ActionName}
      />
      <Text tag="span" color={TextColors.LIGHT_SECONDARY} className={styles.timestamp}>
        {localizeAndFormatTimestamp(eventDetails.timestamp)}
      </Text>
      <Tooltip
        content={
          <Text tag="span" color={TextColors.LIGHT_SECONDARY} className={styles.timestamp}>
            {formatUtcTimestamp(eventDetails.timestamp)}
          </Text>
        }
        size={TooltipSizes.SMALL}
      >
        <span>ⓘ</span>
      </Tooltip>
      <CopyLinkButton link={eventUrl} />
    </div>
  );

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        {cardTitle}
        <OspreyButton onClick={handleShowWindow}>
          See Details
          {showWindow && (
            <NewWindow url={eventUrl} onUnload={handleWindowClose} features={{ width: 800, height: 800 }} />
          )}
        </OspreyButton>
      </div>
      <div>{renderContent()}</div>
    </div>
  );
};

export default EventStreamCard;

```

### `src/components/event_stream/FeatureSelectModal.module.css`

```css
.checkboxGrid {
  display: grid !important;
  grid-row-gap: 8px;
}

.innerCheckboxGrid {
  display: flex;
  flex-direction: column;
}

.category {
  text-transform: capitalize;
}

.featureCheckboxRow {
  padding: 10px 0;
  color: var(--text-light-primary);
}

.featureSpan {
  padding-left: 2px;
  word-break: break-all;
}

.switchSpan {
  display: flex;
  margin-top: 16px;
  padding: 8px 0;
}

.switch {
  margin-right: 8px;
}

.disabled {
  color: var(--text-light-disabled);
}

.featureModal :global(.ant-modal-content) {
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.featureModal :global(.ant-modal-header) {
  padding: 16px;
  margin-bottom: 16px;
  border-bottom: unset;
}

.featureModal :global(.ant-modal-body) {
  overflow: scroll;
}

.featureModal :global(.ant-input-group) {
  position: absolute;
  border-top: 1px solid var(--divider);
  border-bottom: 1px solid var(--divider);
  margin: 0 -16px;
}

.featureModal :global(.ant-input-group-addon) {
  background: unset;
  border: unset;
  padding: unset;
  padding-left: 18px;
  padding-right: 12px;
}

.featureModal :global(.ant-input-affix-wrapper) {
  display: flex;
  border: unset;
  padding: 6px 18px 6px 0;
}

.featureModal :global(.ant-input-affix-wrapper-focused) {
  box-shadow: none;
}

.featureModal :global(.ant-input-affix-wrapper-disabled) {
  background-color: unset;
}

.featureModal :global(.ant-input) {
  font-weight: 500;
  color: var(--text-light-primary);
}

.featureModal :global(.ant-input-search-icon:before) {
  border-left: unset;
}

.featureModal :global(.ant-input-suffix) {
  margin-left: unset;
  margin-right: 12px;
}

.featureModal :global(.ant-input-search-icon) {
  padding: unset;
  margin-left: unset;
}

.featureModal :global(.ant-input-clear-icon) {
  position: absolute;
  right: 16px;
}

.featureModal :global(.ant-checkbox-wrapper + .ant-checkbox-wrapper) {
  margin-left: 0;
}

.featureModal :global(.ant-checkbox-checked .ant-checkbox-inner) {
  background-color: var(--brand-primary);
  border-color: var(--brand-primary);
}

.featureModal :global(.ant-checkbox-inner) {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: none;
  background-color: var(--background-tertiary);
}

.featureModal :global(.ant-checkbox-inner:after) {
  left: 30%;
}

.featureModal :global(.ant-switch-checked) {
  background-color: var(--brand-primary);
}

.featureModal :global(.ant-switch-handle:before) {
  background-image: url('../../assets/CloseIcon.svg');
  background-size: 12px;
  background-repeat: no-repeat;
  background-position: center;
}

.featureModal :global(.ant-switch-checked .ant-switch-handle:before) {
  background-image: url('../../assets/CheckIcon.svg');
  background-size: 12px;
  background-repeat: no-repeat;
  background-position: center;
}

.featureModal :global(.ant-modal-body) {
  padding: 0 16px 16px;
}

.featureModal :global(.ant-modal-footer) {
  background-color: var(--background-secondary-alt);
  padding: 16px 16px 18px;
}

```

### `src/components/event_stream/FeatureSelectModal.tsx`

```typescript
import * as React from 'react';
import { Checkbox, Input, Modal, Switch } from 'antd';
import { CheckboxChangeEvent } from 'antd/lib/checkbox/Checkbox';
import classNames from 'classnames';

import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import useQueryStore from '../../stores/QueryStore';
import OspreyButton from '../../uikit/OspreyButton';
import Text, { TextSizes, TextWeights, TextColors } from '../../uikit/Text';
import FilterIcon from '../../uikit/icons/FilterIcon';
import ModalFooter from '../common/ModalFooter';
import CustomFeaturesFilter from './CustomFeaturesFilter';

import styles from './FeatureSelectModal.module.css';

const FeatureSelectModal = () => {
  const customSummaryFeatures = useQueryStore((state) => state.customSummaryFeatures);
  const updateCustomSummaryFeatures = useQueryStore((state) => state.updateCustomSummaryFeatures);
  const knownFeatureCategories = useApplicationConfigStore((state) => state.knownFeatureCategories);

  const [useCustomFeatures, setUseCustomFeatures] = React.useState(customSummaryFeatures != null);
  const [selectedFeatures, setSelectedFeatures] = React.useState<Set<string>>(
    customSummaryFeatures != null ? new Set(customSummaryFeatures) : new Set()
  );

  const [isOpen, setIsOpen] = React.useState(false);
  const [searchInput, setSearchInput] = React.useState('');

  const sortedKnownFeatureCategoryEntries = React.useMemo(
    () => Object.entries(knownFeatureCategories).sort(),
    [knownFeatureCategories]
  );

  const handleCancel = () => {
    setUseCustomFeatures(customSummaryFeatures != null);
    setSelectedFeatures(customSummaryFeatures != null ? new Set(customSummaryFeatures) : new Set());
    setIsOpen(false);
  };

  const handleOpenModal = () => {
    setIsOpen(true);
  };

  const handleSelectFeature = (e: CheckboxChangeEvent) => {
    const selectedFeature = e.target.value;
    const updatedFeatures = new Set([...selectedFeatures]);

    if (selectedFeatures.has(selectedFeature)) {
      updatedFeatures.delete(selectedFeature);
    } else {
      updatedFeatures.add(selectedFeature);
    }
    setSelectedFeatures(updatedFeatures);
  };

  const handleSaveSelectedFeatures = () => {
    const saveVal = useCustomFeatures ? [...selectedFeatures] : null;

    updateCustomSummaryFeatures(saveVal);
    setIsOpen(false);
  };

  const handleToggleSwitch = () => {
    if (useCustomFeatures) {
      setSelectedFeatures(new Set());
    }

    setUseCustomFeatures(!useCustomFeatures);
  };

  const handleSearchInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchInput(e.currentTarget.value);
  };

  const getReadableFeatureCategory = (featureCategory: string) => {
    return featureCategory.substring(0, featureCategory.lastIndexOf('.')).replace(/_|\//g, ' ');
  };

  const isSetSelected = (feature: string) => {
    if (!useCustomFeatures) return true;

    return selectedFeatures.has(feature as string);
  };

  const renderModalTitle = () => {
    return (
      <>
        <Text size={TextSizes.H4}>Set Features</Text>
        <span className={styles.switchSpan}>
          <Switch
            onChange={handleToggleSwitch}
            className={styles.switch}
            defaultChecked={false}
            checked={useCustomFeatures}
          />
          <Text size={TextSizes.LARGE} weight={TextWeights.NORMAL} color={TextColors.LIGHT_PRIMARY}>
            Set Custom Features
          </Text>
        </span>
        <CustomFeaturesFilter
          selectedCustomFeatures={selectedFeatures}
          useCustomFeatures={useCustomFeatures}
          onClearFilters={() => setSelectedFeatures(new Set())}
          onRemoveSelectedFeature={setSelectedFeatures}
        />
        <Input
          allowClear
          className={styles.__invalid_search}
          disabled={!useCustomFeatures}
          placeholder="Filter feature list"
          onChange={handleSearchInputChange}
          addonBefore={<FilterIcon width={12} height={12} />}
        />
      </>
    );
  };

  const renderFeatureCategory = (category: string, features: string[]) => {
    const filteredFeatures = features.filter((feature) => feature.toUpperCase().includes(searchInput.toUpperCase()));
    if (filteredFeatures.length === 0) return null;

    return (
      <div key={category} className={styles.innerCheckboxGrid}>
        <Text
          size={TextSizes.H5}
          className={classNames(styles.category, {
            [styles.disabled]: !useCustomFeatures,
          })}
        >
          {getReadableFeatureCategory(category)}
        </Text>
        {filteredFeatures.sort().map((feature) => {
          return (
            <Checkbox
              key={feature as string}
              value={feature}
              disabled={!useCustomFeatures}
              onChange={handleSelectFeature}
              checked={isSetSelected(feature)}
              className={styles.featureCheckboxRow}
            >
              <span className={styles.featureSpan}>{feature}</span>
            </Checkbox>
          );
        })}
      </div>
    );
  };

  return (
    <>
      <OspreyButton onClick={handleOpenModal}>Select Summary Features</OspreyButton>
      <Modal
        title={renderModalTitle()}
        className={styles.featureModal}
        width={526}
        open={isOpen}
        onCancel={handleCancel}
        footer={<ModalFooter onOK={handleSaveSelectedFeatures} onCancel={handleCancel} />}
      >
        <div className={styles.checkboxGrid}>
          {sortedKnownFeatureCategoryEntries.map(([category, features]) => {
            return renderFeatureCategory(category, features);
          })}
        </div>
      </Modal>
    </>
  );
};

export default FeatureSelectModal;

```

### `src/components/navigation/NavBar.module.css`

```css
.appWrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.navBar {
  background-color: var(--background-primary);
  height: 42px;
  width: 100%;
  display: flex;
  flex-direction: row;
  align-items: center;
  border-bottom: 2px solid var(--divider);
  position: sticky;
  top: 0;
  z-index: 1;
}

.menuOutlinedIcon {
  font-size: 18px;
  margin-left: 16px;
  margin-right: 12px;
  color: var(--icon-primary);
}

.isRecording :global(.ant-btn.ant-btn-link) {
  user-select: none !important;
}

.navMenuContainer {
  position: absolute;
  width: 250px;
  z-index: 1;
  pointer-events: none;
  height: 100%;
}

.expanded {
  pointer-events: all;
}

.navMenuContainer :global(.ant-menu-inline-collapsed) {
  width: 0 !important;
}

.navMenuContainer :global(.ant-menu-inline-collapsed-noicon) {
  display: none;
}

.navMenuContainer :global(.ant-menu-inline-collapsed) > li {
  padding: 0 !important;
}

.navMenu {
  height: 100%;
}

.contentWrapper {
  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
  position: relative;
  flex-grow: 1;
}

```

### `src/components/navigation/NavBar.tsx`

```typescript
import * as React from 'react';
import { MenuOutlined } from '@ant-design/icons';
import { Menu } from 'antd';
import classNames from 'classnames';
import { Link, useLocation } from 'react-router-dom';

import Logo from '../../assets/Logo';
import useApplicationConfigStore from '../../stores/ApplicationConfigStore';

import { Routes } from '../../Constants';
import styles from './NavBar.module.css';

const NavBar = ({ children }: React.PropsWithChildren) => {
  const [showMenu, setShowMenu] = React.useState(false);
  const location = useLocation();
  const isRecordingClicks = useApplicationConfigStore((state) => state.isRecordingClicks);
  const menuContainerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    let isOpenClick = true;

    function handleWindowClick(e: MouseEvent) {
      // Skip initial click on menu icon that opens menu
      if (isOpenClick) {
        isOpenClick = false;
        return;
      }
      if (
        menuContainerRef.current != null &&
        e.target != null &&
        e.target instanceof Node &&
        !menuContainerRef.current.contains(e.target)
      ) {
        setShowMenu(false);
      }
    }

    if (showMenu) {
      window.addEventListener('click', handleWindowClick);
    }

    return () => window.removeEventListener('click', handleWindowClick);
  }, [menuContainerRef, showMenu]);

  const handleToggleMenu = () => {
    setShowMenu(!showMenu);
  };

  const getSelectedKeys = (): string[] => {
    return [location.pathname];
  };

  return (
    <div className={classNames(styles.appWrapper, { [styles.isRecording]: isRecordingClicks })}>
      <div className={styles.navBar}>
        <MenuOutlined onClick={handleToggleMenu} className={styles.menuOutlinedIcon} />
        <Link to={Routes.HOME}>
          <Logo />
        </Link>
      </div>
      <div className={styles.contentWrapper}>
        <div ref={menuContainerRef} className={classNames(styles.navMenuContainer, { [styles.expanded]: showMenu })}>
          <Menu
            className={styles.navMenu}
            onSelect={handleToggleMenu}
            selectedKeys={getSelectedKeys()}
            mode="inline"
            inlineCollapsed={!showMenu}
          >
            <Menu.Item key={Routes.HOME}>
              <Link to={Routes.HOME}>Home</Link>
            </Menu.Item>
            <Menu.Item key={Routes.QUERY_HISTORY}>
              <Link to={Routes.QUERY_HISTORY}>Query History</Link>
            </Menu.Item>
            <Menu.Item key={Routes.SAVED_QUERIES}>
              <Link to={Routes.SAVED_QUERIES}>Saved Queries</Link>
            </Menu.Item>
            <Menu.Item key={Routes.DOCS_UDFS}>
              <Link to={Routes.DOCS_UDFS}>UDF Documentation</Link>
            </Menu.Item>
            <Menu.Item key={Routes.BULK_JOB_HISTORY}>
              <Link to={Routes.BULK_JOB_HISTORY}>Bulk Job History</Link>
            </Menu.Item>
            <Menu.Item key={Routes.RULES_VISUALIZER}>
              <Link to={Routes.RULES_VISUALIZER}>Rules Visualizer</Link>
            </Menu.Item>
          </Menu>
        </div>
        {children}
      </div>
    </div>
  );
};

export default NavBar;

```

### `src/components/query_history/QueryHistory.module.css`

```css
.viewContainer {
  height: 100%;
  width: 100%;
  max-height: calc(100vh - 42px);
  background-color: var(--background-primary);
  display: flex;
  overflow: hidden;
}

.content {
  width: 100%;
  max-width: 1300px;
  display: flex;
  margin: 0 auto;
}

.header {
  padding: 14px;
  border-bottom: 1px var(--divider) solid;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}

.queryHistoryContainer {
  max-height: 100%;
  width: 70%;
  flex-grow: 1;
  background-color: var(--background-primary);
  border-left: 1px solid var(--divider);
  border-right: 1px solid var(--divider);
  display: flex;
  flex-direction: column;
}

.compactSavedQueriesContainer {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 500px;
  width: 30%;
  margin: 16px;
  border: 1px solid var(--divider);
  border-radius: 8px;
}

.compactHeader {
  height: 40px;
  padding: 8px;
  display: flex;
  align-items: center;
  background-color: var(--background-secondary);
  border-bottom: 1px solid var(--divider);
}

.footer {
  height: 40px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--background-secondary-alt);
  border-top: 1px solid var(--divider);
}

.viewDetailButton:hover {
  background-color: transparent;
}

.viewDetailButton:hover {
  background-color: transparent;
}

```

### `src/components/query_history/QueryHistory.tsx`

```typescript
import * as React from 'react';
import { Link } from 'react-router-dom';

import { getQueryUserEmails } from '../../actions/QueryActions';
import OspreyButton, { ButtonColors } from '../../uikit/OspreyButton';
import Text, { TextSizes } from '../../uikit/Text';
import QueryHistoryIcon from '../../uikit/icons/QueryHistoryIcon';
import IconHeader from '../common/IconHeader';
import UserSelect from '../common/UserSelect';
import QueryHistoryList from '../query_history/QueryHistoryList';
import { SavedQueryCardTypes } from '../saved_queries/SavedQueryCard';
import SavedQueryList from '../saved_queries/SavedQueryList';

import { Routes } from '../../Constants';
import styles from './QueryHistory.module.css';

const QueryHistory = () => {
  const [userEmail, setUserEmail] = React.useState<string | undefined>();

  return (
    <div className={styles.viewContainer}>
      <div className={styles.content}>
        <div className={styles.queryHistoryContainer}>
          <div className={styles.header}>
            <IconHeader size={TextSizes.H4} icon={<QueryHistoryIcon />} title="Query History" />
            <div>
              <UserSelect onSelect={setUserEmail} userResolver={getQueryUserEmails} />
            </div>
          </div>
          <QueryHistoryList userEmail={userEmail} />
        </div>
        <div className={styles.compactSavedQueriesContainer}>
          <div className={styles.compactHeader}>
            <Text size={TextSizes.H5}>Saved Queries</Text>
          </div>
          <SavedQueryList cardType={SavedQueryCardTypes.COMPACT} />
          <div className={styles.footer}>
            <OspreyButton className={styles.viewDetailButton} color={ButtonColors.LINK_GRAY}>
              <Link to={Routes.SAVED_QUERIES}>View all saved queries</Link>
            </OspreyButton>
          </div>
        </div>
      </div>
    </div>
  );
};

export default QueryHistory;

```

### `src/components/query_history/QueryHistoryList.module.css`

```css
.listContainer {
  overflow-y: auto;
  overflow-anchor: none;
}

```

### `src/components/query_history/QueryHistoryList.tsx`

```typescript
import * as React from 'react';
import InfiniteScroll from 'react-infinite-scroller';

import { getQueriesHistory } from '../../actions/QueryActions';
import usePromiseResult from '../../hooks/usePromiseResult';
import useQueryStore from '../../stores/QueryStore';
import { QueryRecord } from '../../types/QueryTypes';
import { renderFromPromiseResult } from '../../utils/PromiseResultUtils';
import SaveQueryModal from '../saved_queries/SaveQueryModal';
import QueryRecordCard, { QueryRecordCardTypes } from './QueryRecordCard';

import styles from './QueryHistoryList.module.css';
import { querySearchContext } from '../query_view/QuerySearchContext';
import { splitStringIncludingMatches } from '../../utils/StringUtils';

const QUERY_BATCH_SIZE = 100;

interface QueryHistoryListProps {
  cardType?: QueryRecordCardTypes;
  userEmail?: string;
}

type QueryHistoryListContentProps = {
  initialQueries: QueryRecord[];
} & QueryHistoryListProps;

const QueryHistoryListContent = ({
  cardType = QueryRecordCardTypes.DETAILED,
  initialQueries,
  userEmail,
}: QueryHistoryListContentProps) => {
  const [offset, setOffset] = React.useState<string | undefined>();
  const [accumulatedQueries, setAccumulatedQueries] = React.useState(initialQueries);
  const [hasMoreQueries, setHasMoreQueries] = React.useState(true);
  const [queryIdToSave, setQueryIdToSave] = React.useState<string | null>(null);
  const searchQuery = React.useContext(querySearchContext);

  React.useEffect(() => {
    let isMounted = true;

    async function fetchMoreQueryHistory() {
      const queries = await getQueriesHistory(userEmail, offset);
      if (!isMounted) return;

      setAccumulatedQueries((prevAccQueries) => [...prevAccQueries, ...queries]);

      if (queries.length === 0 || queries.length % QUERY_BATCH_SIZE !== 0) {
        setHasMoreQueries(false);
      }
    }

    if (offset != null) {
      fetchMoreQueryHistory();
    }

    return () => {
      isMounted = false;
    };
  }, [offset, userEmail]);

  React.useEffect(() => {
    setAccumulatedQueries(accumulatedQueries);
  }, [accumulatedQueries, initialQueries]);

  const handleCancelSave = () => {
    setQueryIdToSave(null);
  };

  const renderQueryRecordCard = (query: QueryRecord) => {
    if (query == null) return null;
    return <QueryRecordCard key={query.id} query={query} onSaveQuery={setQueryIdToSave} type={cardType} />;
  };

  const renderSavedQueryModal = () => {
    if (queryIdToSave == null) return;
    return <SaveQueryModal queryId={queryIdToSave} onCancel={handleCancelSave} />;
  };

  const loadMoreQueries = () => {
    const lastQuery = accumulatedQueries[accumulatedQueries.length - 1];

    if (lastQuery != null && lastQuery.id !== offset) {
      setOffset(lastQuery.id);
    }
  };

  const searchQueryFilter = (value: QueryRecord) => {
    if (!searchQuery || searchQuery.query === '') return true;
    const queryMatches = splitStringIncludingMatches(value.query_filter, searchQuery.query, searchQuery.regex);
    return queryMatches.find((val) => val.matched);
  };

  return (
    <div className={styles.listContainer}>
      {renderSavedQueryModal()}
      <InfiniteScroll pageStart={0} loadMore={loadMoreQueries} hasMore={hasMoreQueries} useWindow={false}>
        {accumulatedQueries.filter(searchQueryFilter).map(renderQueryRecordCard)}
      </InfiniteScroll>
    </div>
  );
};

const QueryHistoryList = ({ cardType = QueryRecordCardTypes.DETAILED, userEmail }: QueryHistoryListProps) => {
  const executedQuery = useQueryStore((state) => state.executedQuery);
  const sortOrder = useQueryStore((state) => state.sortOrder);
  const topNTables = useQueryStore((state) => state.topNTables);

  const queryHistoryResult = usePromiseResult(
    () => getQueriesHistory(userEmail),
    [executedQuery, sortOrder, topNTables, userEmail]
  );

  return renderFromPromiseResult(queryHistoryResult, (queries: QueryRecord[]) => (
    <QueryHistoryListContent cardType={cardType} initialQueries={queries} userEmail={userEmail} />
  ));
};

export default QueryHistoryList;

```

### `src/components/query_history/QueryRecordCard.module.css`

```css
.queryCard {
  width: 100%;
  border-bottom: 1px var(--divider) solid;
}

.sidebar {
  margin-bottom: 8px;
  padding-bottom: 8px;
}

.sidebar:first-child {
  padding-top: 16px;
}

.querySidebarMetadata {
  padding: 8px 16px 0;
}

.actionData {
  padding: 0 16px;
}

.placeholder {
  margin-bottom: 2px;
}

.menuItem {
  color: var(--text-light-primary);
}

.menuItem:hover {
  color: var(--text-light-primary);
}

```

### `src/components/query_history/QueryRecordCard.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';
import { Link } from 'react-router-dom';

import { IntervalOptions, QueryRecord, MomentRangeValues } from '../../types/QueryTypes';
import { MenuOption } from '../../uikit/DropdownMenu';
import { ExpandContextProvider } from '../../uikit/Expand';
import Text from '../../uikit/Text';
import { getIntervalFromDateRange } from '../../utils/DateUtils';
import { getSearchParamsForQueryRecord } from '../../utils/SearchParamUtils';
import IconDropdownMenu from '../common/IconDropdownMenu';
import { QueryCardBody, QueryCardActionData, QueryCardHeader } from '../common/QueryCards';
import QueryRecordCardButtons from './QueryRecordCardButtons';

import { Routes } from '../../Constants';
import styles from './QueryRecordCard.module.css';

export enum QueryRecordCardTypes {
  DETAILED,
  SIDEBAR,
}

interface QueryRecordCardProps {
  query: QueryRecord;
  onSaveQuery: React.Dispatch<React.SetStateAction<string | null>>;
  type: QueryRecordCardTypes;
}

const QueryRecordCard = ({ query, onSaveQuery, type = QueryRecordCardTypes.DETAILED }: QueryRecordCardProps) => {
  const interval = getIntervalFromDateRange(query.date_range);
  const intervalCopy = interval == null ? '' : IntervalOptions[interval as MomentRangeValues].label;
  const isSidebarView = type === QueryRecordCardTypes.SIDEBAR;

  const handleSaveQuery = () => {
    onSaveQuery(query.id);
  };

  const renderQueryCardButtons = () => {
    if (isSidebarView) return null;

    return (
      <QueryRecordCardButtons
        query={query}
        interval={interval}
        intervalCopy={intervalCopy}
        onSaveQuery={handleSaveQuery}
      />
    );
  };

  const getMenuOptions = (): MenuOption[] => {
    const menuOptions = [];

    if (interval != null) {
      const link = (
        <Link
          className={styles.menuItem}
          to={() => ({ pathname: Routes.HOME, search: getSearchParamsForQueryRecord(query, true) })}
        >
          Query {intervalCopy}
        </Link>
      );

      menuOptions.push({ label: link });
    }

    const viewOriginal = (
      <Link className={styles.menuItem} to={{ pathname: Routes.HOME, search: getSearchParamsForQueryRecord(query) }}>
        View Original Query
      </Link>
    );

    menuOptions.push({ label: viewOriginal });
    menuOptions.push({
      label: 'Save Query',
      onClick: handleSaveQuery,
    });

    return menuOptions;
  };

  const queryFilterPlaceholder = isSidebarView ? (
    <Text className={styles.placeholder} italic>
      Empty Query
    </Text>
  ) : null;

  return (
    <ExpandContextProvider>
      <div className={classNames(styles.queryCard, { [styles.sidebar]: isSidebarView })}>
        <QueryCardHeader isCompact={isSidebarView}>
          <QueryCardActionData user={query.executed_by} timestamp={query.executed_at} action="queried at" />
          {isSidebarView ? <IconDropdownMenu options={getMenuOptions()} /> : null}
        </QueryCardHeader>
        <QueryCardBody
          query={query}
          intervalCopy={intervalCopy}
          queryFilterPlaceholder={queryFilterPlaceholder}
          isCompact={isSidebarView}
        />
        {renderQueryCardButtons()}
      </div>
    </ExpandContextProvider>
  );
};

export default QueryRecordCard;

```

### `src/components/query_history/QueryRecordCardButtons.module.css`

```css
.buttonContainer {
  width: 100%;
  display: flex;
  padding: 8px 16px;
  justify-content: space-between;
}

.buttonsLeft {
  display: flex;
}

.originalQueryButton {
  margin-right: 16px;
}

.saveQueryButton {
  background-color: transparent;
  width: 32px;
  height: 32px;
  border-radius: 28px;
  border: 1px solid var(--divider);
  cursor: pointer;
}

```

### `src/components/query_history/QueryRecordCardButtons.tsx`

```typescript
import * as React from 'react';
import { Link } from 'react-router-dom';

import { QueryRecord, MomentRangeValues } from '../../types/QueryTypes';
import OspreyButton from '../../uikit/OspreyButton';
import StarIcon from '../../uikit/icons/StarIcon';
import { getSearchParamsForQueryRecord } from '../../utils/SearchParamUtils';

import { Routes } from '../../Constants';
import styles from './QueryRecordCardButtons.module.css';

interface QueryRecordCardButtonsProps {
  query: QueryRecord;
  interval: MomentRangeValues | null;
  intervalCopy: string;
  onSaveQuery?: () => void;
}

export const QueryRecordCardButtons = ({ query, interval, intervalCopy, onSaveQuery }: QueryRecordCardButtonsProps) => {
  const renderQueryIntervalButton = () => {
    if (interval == null) return null;
    return (
      <OspreyButton>
        <Link to={{ pathname: Routes.HOME, search: getSearchParamsForQueryRecord(query, true) }}>
          Query {intervalCopy}
        </Link>
      </OspreyButton>
    );
  };

  const renderSaveQueryButton = () => {
    if (onSaveQuery == null) return null;

    return (
      <button onClick={onSaveQuery} className={styles.saveQueryButton}>
        <StarIcon />
      </button>
    );
  };

  return (
    <div className={styles.buttonContainer}>
      <div className={styles.buttonsLeft}>
        <OspreyButton className={styles.originalQueryButton}>
          <Link to={{ pathname: Routes.HOME, search: getSearchParamsForQueryRecord(query) }}>View Original Query</Link>
        </OspreyButton>
        {renderQueryIntervalButton()}
      </div>
      {renderSaveQueryButton()}
    </div>
  );
};

export default QueryRecordCardButtons;

```

### `src/components/query_view/QueryDatePicker.module.css`

```css
.datePickerWrapper {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  flex-shrink: 0;
}

.interval {
  cursor: default;
  display: flex;
  align-items: center;
}

.editIcon {
  margin-left: 6px;
  transition: 0.25s ease all;
  cursor: pointer;
}

```

### `src/components/query_view/QueryDatePicker.tsx`

```typescript
import * as React from 'react';
import { EditOutlined } from '@ant-design/icons';
import { DatePicker } from 'antd';
import type { RangePickerProps } from 'antd/es/date-picker';
import dayjs, { type Dayjs } from 'dayjs';

import { DefaultIntervals } from '../../types/QueryTypes';
import Text, { TextColors, TextSizes, TextWeights } from '../../uikit/Text';
import { localizeAndFormatTimestamp } from '../../utils/DateUtils';
import { CUSTOM_RANGE_OPTION, isEmptyDateRange } from '../../utils/QueryUtils';

import { DATE_FORMAT } from '../../Constants';
import styles from './QueryDatePicker.module.css';

interface QueryDatePickerProps {
  onIntervalChange: (interval: DefaultIntervals) => void;
  onDateRangeChange: (dateRange: { start: string; end: string }) => void;
  interval: DefaultIntervals;
  dateRange: { start: string; end: string };
}

type RangePickerValue = [Dayjs, Dayjs];

const QueryDatePicker = ({ onIntervalChange, onDateRangeChange, interval, dateRange }: QueryDatePickerProps) => {
  const handleRangePickerChange: RangePickerProps['onChange'] = (dates, _dateStrings) => {
    if (dates == null) return;

    const start = dates[0];
    const end = dates[1];
    if (start == null || end == null) return;

    // Convert to UTC format for backend API
    onDateRangeChange({ start: start.utc().format(), end: end.utc().format() });
  };

  const handleSwitchToCustomRange = () => {
    onIntervalChange(CUSTOM_RANGE_OPTION);
  };

  const renderQueryIntervalOrDatePicker = () => {
    if (interval === CUSTOM_RANGE_OPTION) {
      const value: RangePickerValue | undefined = isEmptyDateRange(dateRange.start, dateRange.end)
        ? undefined
        : [dayjs(dateRange.start), dayjs(dateRange.end)];

      return (
        <DatePicker.RangePicker
          showTime={{ format: 'hh:mma', use12Hours: true }}
          format={DATE_FORMAT}
          placeholder={['Start Date', 'End Date']}
          onChange={handleRangePickerChange}
          value={value}
        />
      );
    }

    if (isEmptyDateRange(dateRange.start, dateRange.end)) return null;

    return (
      <Text
        className={styles.interval}
        size={TextSizes.SMALL}
        weight={TextWeights.SEMIBOLD}
        color={TextColors.LIGHT_SECONDARY}
      >
        Queried {`${localizeAndFormatTimestamp(dateRange.start)} - ${localizeAndFormatTimestamp(dateRange.end)}`}
        <EditOutlined className={styles.editIcon} onClick={handleSwitchToCustomRange} />
      </Text>
    );
  };

  return <div className={styles.datePickerWrapper}>{renderQueryIntervalOrDatePicker()}</div>;
};

export default QueryDatePicker;

```

### `src/components/query_view/QueryErrors.module.css`

```css
.errorAlertWrapper {
  padding: 10px;
  max-height: 250px;
  overflow: hidden;
}

.errorTooltip {
  width: auto;
}

.errorCount {
  cursor: pointer;
}

.error {
  white-space: pre;
  font-family: monospace;
}

```

### `src/components/query_view/QueryErrors.tsx`

```typescript
import * as React from 'react';
import { Alert } from 'antd';

import useErrorStore from '../../stores/ErrorStore';
import Text, { TextColors, TextWeights } from '../../uikit/Text';
import Tooltip from '../../uikit/Tooltip';
import { Placements } from '../../utils/DOMUtils';

import styles from './QueryErrors.module.css';

const QueryErrors: React.FC = () => {
  const errors = useErrorStore((state) => state.errors);

  const renderErrors = () => {
    const errorList = [...errors].map((error: string, index: number) => (
      <div className={styles.error} key={index}>
        {error}
      </div>
    ));

    return (
      <Tooltip placement={Placements.BOTTOM_LEFT} className={styles.errorTooltip} content={errorList} defaultVisible>
        <Text className={styles.errorCount} tag="span" color={TextColors.LINK_BLUE} weight={TextWeights.SEMIBOLD}>
          {`Error${errors.size > 1 ? 's' : ''}`}
        </Text>
      </Tooltip>
    );
  };

  return errors.size === 0 ? null : (
    <div className={styles.errorAlertWrapper}>
      <Alert
        type="error"
        message={
          <>
            {`${errors.size} `}
            {renderErrors()}
            {` Found`}
          </>
        }
      />
    </div>
  );
};

export default QueryErrors;

```

### `src/components/query_view/QueryInput.module.css`

```css
.queryInput {
  padding: 8px 16px;
  z-index: 2;
  border-bottom: 2px solid var(--divider);
  background-color: var(--background-primary);
}

.textareaWrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 8px;
  position: relative;
}

.textareaWrapper :global(.ant-input.ant-select-selection-search-input) {
  background-color: var(--background-secondary);
  border-color: var(--divider);
}

.textareaWrapper :global(.ant-input) {
  box-shadow: none !important;
  min-height: 80px !important;
}

.autoComplete {
  width: 100%;
}

.autoComplete textarea {
  overflow-x: hidden;
  font-size: 12px;
  line-height: 20px;
  font-weight: 500;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
  color: transparent;
  caret-color: var(--text-light-primary);
}

.submitButton {
  width: 100%;
  border: 0;
}

.overlay {
  position: absolute;
  height: 100%;
  width: 100%;
  top: 0;
  pointer-events: none;
  font-size: 12px;
  padding: 4px 11px;
  border: 1px solid transparent;
}

.highlightedWrap {
  overflow-wrap: break-word;
}

.displayArea {
  white-space: pre-wrap;
}

.intervalSelect :global(.ant-select) {
  width: 100% !important;
}

.intervalSelect :global(.ant-select-selector) {
  color: var(--text-light-secondary);
  height: 26px !important;
  --antd-wave-shadow-color: none !important;
  box-shadow: none !important;
  margin-bottom: 8px;
  border-top: none !important;
  border-color: var(--divider) !important;
  border-radius: 0 0 4px 4px !important;
  background-color: var(--background-secondary) !important;
  font-weight: 700 !important;
}

.intervalSelect :global(.ant-select-selection-item) {
  line-height: 26px !important;
}

.intervalSelect :global(.ant-select-arrow) {
  margin-top: -10px !important;
}

```

### `src/components/query_view/QueryInput.tsx`

```typescript
import * as React from 'react';
import { AutoComplete, Input, Select } from 'antd';

import { SelectValue } from 'antd/lib/select';
import { OptionData } from 'rc-select/lib/interface/index';

import shallow from 'zustand/shallow';

import { validateQuery } from '../../actions/QueryActions';
import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import useErrorStore from '../../stores/ErrorStore';
import useQueryStore from '../../stores/QueryStore';
import { IntervalOptions, DefaultIntervals } from '../../types/QueryTypes';
import OspreyButton, { ButtonColors } from '../../uikit/OspreyButton';
import { TextSizes } from '../../uikit/Text';
import QueryIcon from '../../uikit/icons/QueryIcon';
import { filterAutoComplete, sortOptions } from '../../utils/AutoCompleteUtils';
import { getQueryDateRange, isEmptyDateRange, CUSTOM_RANGE_OPTION } from '../../utils/QueryUtils';
import IconHeader from '../common/IconHeader';
import QueryFilter from '../common/QueryFilter';
import OptionLabelWithInfo from '../common/OptionLabelWithInfo';
import QueryErrors from './QueryErrors';

import styles from './QueryInput.module.css';

const SelectOptions = [
  ...Object.entries(IntervalOptions).map(([option, { label }]) => ({
    value: option,
    label: label,
  })),
  { value: CUSTOM_RANGE_OPTION, label: 'Custom Range' },
];

export interface QueryInputProps {
  interval: DefaultIntervals;
  dateRange: { start: string; end: string };
  onIntervalChange: (interval: DefaultIntervals) => void;
}

const QueryInput = ({
  interval: executedQueryInterval,
  onIntervalChange: onExecutedQueryIntervalChange,
  dateRange,
}: QueryInputProps) => {
  const [executedQuery, updateExecutedQuery] = useQueryStore(
    (state) => [state.executedQuery, state.updateExecutedQuery],
    shallow
  );
  const [knownFeatureNames, knownActionNames, ruleInfoMapping] = useApplicationConfigStore(
    (state) => [state.knownFeatureNames, state.knownActionNames, state.ruleInfoMapping],
    shallow
  );
  const [queryFilter, setQueryFilter] = React.useState(executedQuery.queryFilter);
  const [searchOptions, setSearchOptions] = React.useState<OptionData[]>([]);
  const [filteredOptions, setFilteredOptions] = React.useState<OptionData[]>([]);

  // store the selected interval state separate from the current query's interval, so that changes
  // to the interval can be made without losing WIP in the query input field
  const [selectedInterval, setSelectedInterval] = React.useState(executedQueryInterval);

  const [isLoading, setIsLoading] = React.useState(false);

  const handleSelectChange = (value: DefaultIntervals) => {
    // only update the active query's interval if the user has not made any changes to their query input
    if (executedQuery.queryFilter === queryFilter) {
      onExecutedQueryIntervalChange(value);
    }
    setSelectedInterval(value);
  };

  React.useEffect(() => {
    const options = [...knownFeatureNames, ...knownActionNames].map((option: string) => ({
      value: option,
      label: <OptionLabelWithInfo option={option} optionInfoMapping={ruleInfoMapping} />,
    }));
    setSearchOptions(options);
    setFilteredOptions(options);
  }, [knownFeatureNames, knownActionNames]);

  React.useEffect(() => {
    setQueryFilter(executedQuery.queryFilter);
    // if the user has selected a new query to execute from the saved queries list, make sure that
    // we update the selected interval to reflect the correct one
    if (executedQuery.interval !== selectedInterval) {
      setSelectedInterval(executedQuery.interval);
    }
  }, [executedQuery, selectedInterval]);

  const handleSelectAutoComplete = (value: SelectValue) => {
    let insertValue = String(value);

    if (knownActionNames.has(insertValue)) {
      insertValue = `"${insertValue}"`;
    }

    const textAreaValueArr = queryFilter.split(' ');
    textAreaValueArr[textAreaValueArr.length - 1] = insertValue;
    const newTextAreaValue = textAreaValueArr.join(' ');

    setQueryFilter(newTextAreaValue);
  };

  const clearErrors = useErrorStore((state) => state.clearErrors);

  const handleSubmitQuery = async () => {
    setIsLoading(true);
    clearErrors();
    const isValid = queryFilter === '' ? true : await validateQuery(queryFilter);

    if (isValid) {
      const { start, end } = getQueryDateRange(selectedInterval, dateRange);
      updateExecutedQuery({ start, end, queryFilter, interval: selectedInterval });
    }

    setIsLoading(false);
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const ctrlOrMetaKey = e.ctrlKey || e.metaKey;
    if (ctrlOrMetaKey && e.key === 'Enter') {
      handleSubmitQuery();
    }
  };

  const handleTextAreaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setQueryFilter(e.target.value);
    handleSearch(e.target.value);
  };

  const handleSearch = (inputValue: string) => {
    const currentWord = String(inputValue.split(' ').slice(-1));
    const filtered = searchOptions
      .filter((option) => filterAutoComplete(inputValue, option))
      .sort(sortOptions(currentWord));

    setFilteredOptions(filtered);
  };

  return (
    <div className={styles.queryInput}>
      <IconHeader size={TextSizes.H4} icon={<QueryIcon />} title="Query" />
      <div className={styles.textareaWrapper}>
        <AutoComplete
          className={styles.autoComplete}
          value={queryFilter}
          options={filteredOptions}
          onSelect={handleSelectAutoComplete}
        >
          <Input.TextArea
            className={styles.__invalid_textArea}
            onChange={handleTextAreaChange}
            onPressEnter={handleKeyPress}
            autoSize={{ minRows: 2 }}
            spellCheck="false"
          />
        </AutoComplete>
        <div className={styles.overlay}>
          <QueryFilter
            queryFilter={queryFilter}
            className={styles.highlightedWrap}
            codeClassName={styles.displayArea}
          />
        </div>
      </div>
      <div className={styles.intervalSelect}>
        <Select
          onChange={handleSelectChange}
          placeholder="Select date range"
          style={{ width: 180 }}
          value={selectedInterval ?? undefined}
        >
          {SelectOptions.map((option) => (
            <Select.Option value={option.value} key={option.value}>
              {option.label}
            </Select.Option>
          ))}
        </Select>
      </div>
      <OspreyButton
        disabled={selectedInterval === CUSTOM_RANGE_OPTION && isEmptyDateRange(dateRange.start, dateRange.end)}
        color={ButtonColors.DARK_BLUE}
        className={styles.submitButton}
        onClick={handleSubmitQuery}
        loading={isLoading}
      >
        Submit Query
      </OspreyButton>
      <QueryErrors />
    </div>
  );
};

export default QueryInput;

```

### `src/components/query_view/QueryListPanel.module.css`

```css
.menuWrapper {
  background-color: var(--background-primary);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-right: 16px;
}

.filterSelect {
  width: 120px;
}

.menuWrapper :global(.ant-menu) {
  line-height: 38px;
}

.menuWrapper :global(.ant-menu) :global(.ant-menu-item) {
  font-weight: 600;
}

.menuWrapper :global(.ant-menu) :global(.ant-menu-item):hover {
  color: var(--brand-primary);
  border-bottom: 2px solid var(--brand-primary);
}

.menuWrapper :global(.ant-menu) :global(.ant-menu-item.ant-menu-item-selected) {
  color: var(--brand-primary);
  border-bottom: 2px solid var(--brand-primary);
}

.regexButton {
  --color: black;
  margin: 0;
  padding: 0 6px;
  background: none;
  border: 1px solid color-mix(in srgb, var(--color), transparent 80%);
  color: color-mix(in srgb, var(--color), transparent 60%);
  border-radius: 4px;
  transition: all 0.2s ease;
  &:hover {
    background: color-mix(in srgb, var(--color), transparent 95%);
    border: 1px solid color-mix(in srgb, var(--color), transparent 75%);
    color: color-mix(in srgb, var(--color), transparent 50%);
  }
  &[data-enabled='true'] {
    border: 1px solid color-mix(in srgb, var(--brand-primary), transparent 30%);
    &:hover {
      border: 1px solid color-mix(in srgb, var(--brand-primary), transparent 60%);
    }
  }
}

```

### `src/components/query_view/QueryListPanel.tsx`

```typescript
import * as React from 'react';
import { Input, Menu, Select } from 'antd';

import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import QueryHistoryList from '../query_history/QueryHistoryList';
import { QueryRecordCardTypes } from '../query_history/QueryRecordCard';
import { SavedQueryCardTypes } from '../saved_queries/SavedQueryCard';
import SavedQueryList from '../saved_queries/SavedQueryList';

import { querySearchContext } from './QuerySearchContext';

import styles from './QueryListPanel.module.css';

enum QueryListPanelTabs {
  HISTORY = 'HISTORY',
  SAVED_QUERIES = 'SAVED_QUERIES',
}

enum QueryListFilterOptions {
  ALL = 'ALL',
  MINE = 'MINE',
}

const QueryListPanel = () => {
  const currentUser = useApplicationConfigStore((state) => state.currentUser);
  const [selectedTab, setSelectedTab] = React.useState(QueryListPanelTabs.HISTORY);
  const [filterOption, setFilterOption] = React.useState(QueryListFilterOptions.ALL);
  const [search, setSearch] = React.useState('');
  const [regexEnabled, setRegexEnabled] = React.useState(false);
  const handleMenuItemClick = (e: { key: React.Key }) => {
    setSelectedTab(e.key as QueryListPanelTabs);
  };

  const renderQueryList = () => {
    let user;

    if (filterOption === QueryListFilterOptions.MINE) {
      user = currentUser;
    }

    switch (selectedTab) {
      case QueryListPanelTabs.HISTORY:
        return <QueryHistoryList userEmail={user?.email} cardType={QueryRecordCardTypes.SIDEBAR} />;
      case QueryListPanelTabs.SAVED_QUERIES:
        return (
          <SavedQueryList
            userEmail={user?.email}
            cardType={search.length ? SavedQueryCardTypes.DETAILED : SavedQueryCardTypes.COMPACT}
          />
        );
    }
  };

  return (
    <>
      <RegexSearchInput
        query={search}
        setQuery={setSearch}
        regexEnabled={regexEnabled}
        setRegexEnabled={setRegexEnabled}
      />
      <querySearchContext.Provider value={{ query: search, regex: regexEnabled }}>
        <div className={styles.menuWrapper}>
          <Menu onClick={handleMenuItemClick} mode="horizontal" selectedKeys={[selectedTab]}>
            <Menu.Item key={QueryListPanelTabs.HISTORY}>History</Menu.Item>
            <Menu.Item key={QueryListPanelTabs.SAVED_QUERIES}>Saved Queries</Menu.Item>
          </Menu>
          <Select onChange={setFilterOption} className={styles.filterSelect} defaultValue={QueryListFilterOptions.ALL}>
            <Select.Option value={QueryListFilterOptions.ALL}>All</Select.Option>
            <Select.Option value={QueryListFilterOptions.MINE}>My Queries</Select.Option>
          </Select>
        </div>
        {renderQueryList()}
      </querySearchContext.Provider>
    </>
  );
};

export default QueryListPanel;

const RegexToggleButton = ({
  regexEnabled,
  setRegexEnabled,
}: {
  regexEnabled: boolean;
  setRegexEnabled: (regex: boolean) => void;
}) => {
  return (
    <button
      onClick={() => setRegexEnabled(!regexEnabled)}
      title={regexEnabled ? 'Disable RegEx' : 'Enable RegEx'}
      data-enabled={regexEnabled}
      className={styles.regexButton}
    >
      .*
    </button>
  );
};
type RegexSearchInputProps = {
  query: string;
  setQuery: (query: string) => void;
  regexEnabled: boolean;
  setRegexEnabled: (regex: boolean) => void;
};
const RegexSearchInput = ({ query, regexEnabled, setQuery, setRegexEnabled }: RegexSearchInputProps) => {
  return (
    <Input.Search
      value={query}
      onInput={(e) => setQuery(e.currentTarget.value)}
      prefix={<span style={{ color: '#00000050', width: '1ch' }}>{regexEnabled ? '/' : ''}</span>}
      suffix={
        <>
          <span style={{ color: '#00000050', width: '2ch' }}>{regexEnabled ? '/g' : ''}</span>
          <RegexToggleButton regexEnabled={regexEnabled} setRegexEnabled={setRegexEnabled} />
        </>
      }
    />
  );
};

```

### `src/components/query_view/QueryPanel.module.css`

```css
.queryPanel {
  padding: 8px 16px;
  z-index: 2;
  border-bottom: 2px solid var(--divider);
  background-color: var(--background-primary);
}

.textareaWrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 8px;
  position: relative;
}

.textareaWrapper :global(.ant-input.ant-select-selection-search-input) {
  background-color: var(--background-secondary);
  border-color: var(--divider);
}

.textareaWrapper :global(.ant-input) {
  box-shadow: none !important;
  min-height: 80px !important;
}

.autoComplete {
  width: 100%;
}

.autoComplete textarea {
  overflow-x: hidden;
  font-size: 12px;
  line-height: 20px;
  font-weight: 500;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
  color: transparent;
  caret-color: var(--text-light-primary);
}

.submitButton {
  width: 100%;
  border: 0;
}

.overlay {
  position: absolute;
  height: 100%;
  width: 100%;
  top: 0;
  pointer-events: none;
  font-size: 12px;
  padding: 4px 11px;
  border: 1px solid transparent;
}

.highlightedWrap {
  overflow-wrap: break-word;
}

.displayArea {
  white-space: pre-wrap;
}

.intervalSelect :global(.ant-select) {
  width: 100% !important;
}

.intervalSelect :global(.ant-select-selector) {
  color: var(--text-light-secondary);
  height: 26px !important;
  --antd-wave-shadow-color: none !important;
  box-shadow: none !important;
  margin-bottom: 8px;
  border-top: none !important;
  border-color: var(--divider) !important;
  border-radius: 0 0 4px 4px !important;
  background-color: var(--background-secondary) !important;
  font-weight: 700 !important;
}

.intervalSelect :global(.ant-select-selection-item) {
  line-height: 26px !important;
}

.intervalSelect :global(.ant-select-arrow) {
  margin-top: -10px !important;
}

```

### `src/components/query_view/QueryPanel.tsx`

```typescript
import * as React from 'react';
import { Route, Switch } from 'react-router-dom';

import EntityPanel from '../entities/EntityPanel';
import QueryInput, { QueryInputProps } from './QueryInput';
import QueryListPanel from './QueryListPanel';

import { Routes } from '../../Constants';
import 'highlight.js/styles/atelier-cave-light.css';

interface QueryPanelProps {}

const QueryPanel = ({ ...props }: QueryPanelProps & QueryInputProps) => {
  return (
    <>
      <QueryInput {...props} />
      <Switch>
        <Route path={Routes.ENTITY}>
          <EntityPanel />
        </Route>
        <Route>
          <QueryListPanel />
        </Route>
      </Switch>
    </>
  );
};

export default QueryPanel;

```

### `src/components/query_view/QuerySearchContext.tsx`

```typescript
import React, { createContext } from 'react';

export const querySearchContext = createContext<{ query: string; regex: boolean }>({ query: '', regex: false });

```

### `src/components/query_view/QueryView.module.css`

```css
.queryView {
  width: 100%;
  background-color: var(--background-secondary);
  display: flex;
  flex-direction: row;
  margin: 0 auto;
  flex-grow: 1;
}

.datePickerBar {
  display: flex;
  align-items: center;
  background-color: var(--background-secondary);
  overflow: hidden;
  transition: 0.2s ease all;
}

.datePickerBarShown {
  composes: datePickerBar;
  height: 42px;
  padding: 8px 16px;
  border-bottom: 2px solid var(--divider);
}

.datePickerBarHidden {
  composes: datePickerBar;
  height: 0;
}

.charts {
  display: flex;
  flex-grow: 1;
}

.pageContentLeft {
  width: 420px;
  max-width: 420px;
  min-width: 420px;
  max-height: calc(100vh - 42px);
  border-right: 2px solid var(--divider);
  flex-grow: 1;
  position: sticky;
  top: 42px;
  display: flex;
  flex-direction: column;
  background-color: var(--background-secondary-alt);
}

.pageContentRight {
  width: 80%;
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

.chartsLeft {
  min-width: 500px;
  width: 40%;
  display: flex;
  flex-direction: column;
  border-right: 2px solid var(--divider);
}

.chartsRight {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

.pageContentLeft > :global(.ant-menu) {
  background-color: inherit;
}

```

### `src/components/query_view/QueryView.tsx`

```typescript
import * as React from 'react';
import { Route, RouteComponentProps } from 'react-router-dom';

import useQueryStore from '../../stores/QueryStore';
import { DefaultIntervals } from '../../types/QueryTypes';
import { startRecordingClicks, stopRecordingClicks } from '../../utils/EventListenerUtils';
import { getQueryDateRange, CUSTOM_RANGE_OPTION } from '../../utils/QueryUtils';
import BulkLabelDrawer from '../bulk_label_drawer/BulkLabelDrawer';
import EntityFeatureFilters from '../entities/EntityFeatureFilters';
import FeatureFiltersDetailBar from '../entities/FeatureFiltersDetailBar';
import EntityDrawer from '../entities/LabelDrawer';
import EventStream from '../event_stream/EventStream';
import Timeseries from '../timeseries/Timeseries';
import TopN from '../top_n/TopN';
import Charts from '../charts/Charts';
import QueryDatePicker from './QueryDatePicker';
import QueryPanel from './QueryPanel';

import { Routes } from '../../Constants';
import styles from './QueryView.module.css';

const QueryView: React.FC = () => {
  const executedQuery = useQueryStore((state) => state.executedQuery);
  const updateExecutedQuery = useQueryStore((state) => state.updateExecutedQuery);
  const [interval, setQueryInterval] = React.useState(executedQuery.interval);
  const [dateRange, setDateRange] = React.useState({ start: executedQuery.start, end: executedQuery.end });

  React.useEffect(() => {
    setQueryInterval(executedQuery.interval);
    setDateRange({ start: executedQuery.start, end: executedQuery.end });
  }, [executedQuery]);

  React.useEffect(() => {
    document.addEventListener('keydown', startRecordingClicks);
    document.addEventListener('keyup', stopRecordingClicks);

    return () => {
      document.removeEventListener('keydown', startRecordingClicks);
      document.removeEventListener('keyup', stopRecordingClicks);
    };
  }, []);

  const isDateRangeEmpty = (): boolean => {
    return dateRange.start === '' && dateRange.end === '';
  };

  const handleIntervalChange = (interval: DefaultIntervals | 'custom' | null) => {
    setQueryInterval(interval);

    if (interval !== CUSTOM_RANGE_OPTION)
      updateExecutedQuery({ ...executedQuery, interval, ...getQueryDateRange(interval) });
  };

  const handleDateRangeChange = (updatedDateRange: { start: string; end: string }) => {
    setDateRange(updatedDateRange);
    updateExecutedQuery({ ...executedQuery, interval, ...updatedDateRange });
  };

  return (
    <>
      <div className={styles.queryView}>
        <div className={styles.pageContentLeft}>
          <QueryPanel onIntervalChange={handleIntervalChange} interval={interval} dateRange={dateRange} />
        </div>
        <div className={styles.pageContentRight}>
          <div className={isDateRangeEmpty() ? styles.datePickerBarHidden : styles.datePickerBarShown}>
            <QueryDatePicker
              onIntervalChange={handleIntervalChange}
              onDateRangeChange={handleDateRangeChange}
              interval={interval}
              dateRange={dateRange}
            />
            <Route
              path={Routes.ENTITY}
              // @ts-expect-error (yarn.lock upgrade)
              render={({ match }: RouteComponentProps<{ entityId: string; entityType: string }>) => (
                <EntityFeatureFilters {...match.params} />
              )}
            />
          </div>
          <Route path={Routes.ENTITY}>
            <FeatureFiltersDetailBar />
          </Route>
          <div className={styles.charts}>
            <div className={styles.chartsLeft}>
              <Timeseries />
              <Charts />
              <TopN />
            </div>
            <div className={styles.chartsRight}>
              <EventStream />
            </div>
          </div>
          <BulkLabelDrawer />
          <EntityDrawer />
        </div>
      </div>
    </>
  );
};

export default QueryView;

```

### `src/components/rules_visualizer/HierarchicalGraph.module.css`

```css
.cyContainer {
  height: 100%;
}

```

### `src/components/rules_visualizer/HierarchicalGraph.tsx`

```typescript
import { memo, MutableRefObject, ReactElement, useEffect, useRef } from 'react';
import * as ReactDOM from 'react-dom/client';
import cytoscape, { Css, NodeSingular } from 'cytoscape';
import dagre, { DagreLayoutOptions } from 'cytoscape-dagre';
import popper from 'cytoscape-popper';
import tippy from 'tippy.js';

import { HierarchicalGraphOptions } from '../../types/RulesVisualizerTypes';

import 'tippy.js/dist/tippy.css';
import styles from './HierarchicalGraph.module.css';

const defaultNodeStyle: Css.Node = {
  'text-wrap': 'wrap',
  'text-valign': 'bottom',
  color: '#3c3c40',
};

const defaultEdgeStyle: Css.Edge = {
  width: 1,
  'target-arrow-shape': 'triangle',
  'line-color': '#9dbaea',
  'target-arrow-color': '#9dbaea',
  'curve-style': 'bezier',
};

const defaultlayoutOptions: DagreLayoutOptions = {
  name: 'dagre',
  fit: true,
  avoidOverlap: true,
  nodeDimensionsIncludeLabels: true,
  rankDir: 'LR',
};

cytoscape.use(dagre);
cytoscape.use(popper);

const HierarchicalGraph = ({
  elements,
  nodeStyle = {},
  edgeStyle = {},
  layoutOptions = {},
  onLoad = () => {},
  ToolTip,
}: HierarchicalGraphOptions) => {
  const containerRef = useRef(null);
  const toolTipRef = useRef(null);
  const tooltipRootRef = useRef<ReactDOM.Root | null>(null);

  useEffect(() => {
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: { ...defaultNodeStyle, ...nodeStyle },
        },
        {
          selector: 'edge',
          style: { ...defaultEdgeStyle, ...edgeStyle },
        },
      ],
      layout: { ...defaultlayoutOptions, ...layoutOptions },
      maxZoom: 10,
      autoungrabify: true,
    });
    onLoad(cy);

    let tip: any;
    if (ToolTip) {
      cy.nodes().bind('mouseover', (event) => {
        tip = renderToolTipWithTippy(event.target as NodeSingular, ToolTip, containerRef, toolTipRef, tooltipRootRef);
      });
      cy.nodes().bind('mouseout', () => {
        if (tip) {
          tip.destroy();
          tooltipRootRef.current?.unmount();
          tooltipRootRef.current = null;
        }
      });
    }

    return () => {
      if (tip) {
        tip.destroy();
        tooltipRootRef.current?.unmount();
        tooltipRootRef.current = null;
      }
      cy.nodes().unbind('mouseover');
      cy.nodes().unbind('mouseout');
      cy.destroy();
    };
  }, [elements, nodeStyle, edgeStyle, layoutOptions, onLoad, ToolTip]);

  return (
    <>
      <div ref={containerRef} className={styles.cyContainer} />
      <div ref={toolTipRef} />
    </>
  );
};

function renderToolTipWithTippy(
  node: NodeSingular,
  ToolTip: ({ node }: { node: NodeSingular }) => ReactElement,
  containerRef: MutableRefObject<null>,
  toolTipRef: MutableRefObject<null>,
  tooltipRootRef: MutableRefObject<ReactDOM.Root | null>
) {
  const popperRef = node.popperRef();
  if (toolTipRef.current) {
    tooltipRootRef.current = ReactDOM.createRoot(toolTipRef.current);
    tooltipRootRef.current.render(<ToolTip node={node} />);
  }
  if (containerRef.current && toolTipRef.current) {
    const tip: any = tippy(containerRef.current, {
      getReferenceClientRect: popperRef.getBoundingClientRect,
      content: toolTipRef.current,
      placement: 'bottom',
      arrow: true,
    });
    tip.show();
    return tip;
  }
}

export default memo(HierarchicalGraph, (prevProps, nextProps) => {
  return (
    JSON.stringify(prevProps.elements) == JSON.stringify(nextProps.elements) &&
    prevProps.nodeStyle == nextProps.nodeStyle &&
    prevProps.edgeStyle == nextProps.edgeStyle &&
    prevProps.layoutOptions == nextProps.layoutOptions &&
    prevProps.ToolTip == nextProps.ToolTip
  );
});

```

### `src/components/rules_visualizer/RulesVisualizer.module.css`

```css
.viewContainer {
  height: 100%;
  width: 100%;
  display: flex;
  overflow: hidden;
  flex-direction: column;
  background-color: var(--background-primary);
}

.recenterButton {
  position: absolute;
  bottom: 60px;
  right: 60px;
  box-shadow:
    0 3px 6px -4px #0000001f,
    0 6px 16px #00000014,
    0 9px 28px 8px #0000000d;
}

.graphContainer {
  position: relative;
  width: 100%;
  height: 100%;
}

.recenterCard {
  position: absolute;
  top: 10px;
  left: 10px;
  width: 250px;
  z-index: 50;
  box-shadow:
    0 3px 6px -4px #0000001f,
    0 6px 16px #00000014,
    0 9px 28px 8px #0000001d;
}

.recenterButton:focus:not(:hover) {
  color: unset;
  border-color: unset;
}

.centered {
  position: absolute;
  top: 40%;
  left: 50%;
  transform: translateX(-50%);
}

```

### `src/components/rules_visualizer/RulesVisualizer.tsx`

```typescript
import { useState } from 'react';
import { Alert, Button, Card, Spin, Switch } from 'antd';
import { AimOutlined } from '@ant-design/icons';
import shallow from 'zustand/shallow';
import { Css, Core } from 'cytoscape';

import useRulesVisualizerStore from '../../stores/RulesVisualizerStore';
import HierarchicalGraph from './HierarchicalGraph';
import RulesVisualizerHeader from './RulesVisualizerHeader';
import { Node, NodeType, LabelType } from '../../types/RulesVisualizerTypes';

import styles from './RulesVisualizer.module.css';
import { getGraphJson } from '../../actions/RulesVisualizerActions';

export const DEFAULT_ANIMATE_DURATION = 1000;

const typeToShape: Record<string, Css.NodeShape> = {
  [NodeType.Label]: 'ellipse',
  [NodeType.Rule]: 'round-rectangle',
};

const nodeStyle: Css.Node = {
  content: 'data(label)',
  'background-color': (node) => getNodeColor(node.data('type'), node.data('label_type')),
  shape: (node) => typeToShape[node.data('type')],
};

const ToolTip = ({ node }: { node: any }) => {
  return <div>{node.data('file_path')}</div>;
};

const RulesVisualizerView = () => {
  const [updateRuleVizGraph, nodes, edges, selectedFeature, selectedFeatureType, errorMessage] =
    useRulesVisualizerStore(
      (state) => [
        state.updateRuleVizGraph,
        state.nodes,
        state.edges,
        state.selectedFeature,
        state.selectedFeatureType,
        state.errorMessage,
      ],
      shallow
    );
  const [isLoading, setIsLoading] = useState(false);
  const [showLabelUpstream, setShowLabelUpstream] = useState(false);
  const [showLabelDownstream, setShowLabelDownstream] = useState(true);
  const [cyto, setCyto] = useState<Core | null>(null);

  const elements = {
    nodes: (nodes || []).map((node) => ({
      data: {
        id: `${node.id}`,
        label: getLabel(node),
        type: node.type,
        label_type: node.label_type,
        label_name: node.label_name,
        entity_name: node.entity_name,
        file_path: node.file_path,
      },
    })),
    edges: (edges || []).map((edge, idx) => ({
      data: {
        id: `edge-${idx}`,
        source: `${edge.source}`,
        target: `${edge.target}`,
      },
    })),
  };

  let alert;
  if (nodes && !nodes.length) {
    alert = <Alert className={styles.centered} type="warning" message="No associated nodes were found." />;
  } else if (errorMessage) {
    alert = <Alert className={styles.centered} type="error" message={`Error: ${errorMessage}. Please try again.`} />;
  }

  const onGraphLoad = (cy: Core) => {
    // View defaults to fitting whole graph within viewport. Disable zooming out past that.
    cy.minZoom(cy.zoom());
    setCyto(cy);
  };

  const recenterOnClick = () => {
    if (cyto) {
      cyto.animate({
        easing: 'ease-in-out',
        duration: DEFAULT_ANIMATE_DURATION,
        fit: { eles: cyto.elements(), padding: 0 },
      });
    }
  };

  const onShowLabelUpstreamToggle = async (checked: boolean) => {
    setShowLabelUpstream(checked);
    await rerenderLabelViewGraph(checked, showLabelDownstream);
  };

  const onShowLabelDownstreamToggle = async (checked: boolean) => {
    setShowLabelDownstream(checked);
    await rerenderLabelViewGraph(showLabelUpstream, checked);
  };

  const rerenderLabelViewGraph = async (show_upstream: boolean, show_downstream: boolean) => {
    if (!selectedFeature || !selectedFeatureType) {
      return;
    }
    setIsLoading(true);
    updateRuleVizGraph({ nodes: null, edges: null });
    const graphJson = await getGraphJson(
      selectedFeatureType.toLowerCase(),
      [`${selectedFeature}`],
      show_upstream,
      show_downstream
    );
    updateRuleVizGraph(graphJson);
    setIsLoading(false);
  };

  return (
    <div className={styles.viewContainer}>
      <RulesVisualizerHeader
        cy={cyto}
        setIsLoading={setIsLoading}
        showLabelUpstream={showLabelUpstream}
        showLabelDownstream={showLabelDownstream}
      />
      <Spin className={styles.centered} size="large" spinning={isLoading} />
      {alert}
      <div className={styles.graphContainer}>
        {selectedFeatureType === 'Label' && (
          <Card size="small" title="Label View Filters" className={styles.recenterCard}>
            <Switch onChange={onShowLabelUpstreamToggle} disabled={isLoading} defaultChecked={showLabelUpstream} /> Show
            Upstream Nodes
            <br></br>
            <Switch
              onChange={onShowLabelDownstreamToggle}
              disabled={isLoading}
              defaultChecked={showLabelDownstream}
            />{' '}
            Show Downstream Nodes
          </Card>
        )}
        <HierarchicalGraph elements={elements} nodeStyle={nodeStyle} onLoad={onGraphLoad} ToolTip={ToolTip} />
        {nodes && !!nodes.length && (
          <Button
            className={styles.recenterButton}
            shape="circle"
            icon={<AimOutlined />}
            size="large"
            onClick={recenterOnClick}
          />
        )}
      </div>
    </div>
  );
};

function getLabel(node: Node) {
  if (node.type === NodeType.Label) {
    return `${node.type} [${getLabelTypeName(node.label_type)}]\n${node.label_name}\non ${
      node.entity_name ? node.entity_name : 'Unassigned'
    }`;
  }
  return `${node.type}\n${node.value}`;
}

function getLabelTypeName(label_type?: string) {
  const labelTypeName = Object.entries(LabelType).find(([key, value]) => value === label_type);
  return labelTypeName?.[0] || '';
}

function getNodeColor(type: string, label_type?: string) {
  if (type === NodeType.Label && label_type == LabelType.Check) {
    return '#DEA39E';
  } else if (type === NodeType.Label && label_type == LabelType.Add) {
    return '#D4DE9E';
  } else if (type === NodeType.Label && label_type == LabelType.Remove) {
    return '#BC916E';
  } else if (type === NodeType.Rule) {
    return '#CAE0F9';
  }
  return '#8F8F8F';
}

export default RulesVisualizerView;

```

### `src/components/rules_visualizer/RulesVisualizerHeader.module.css`

```css
.autocomplete {
  width: 510px;
}

.header {
  padding: 1rem;
  border-bottom: 1px var(--divider) solid;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  position: relative;
}

.leftHeaderContainer {
  flex: 3;
}

.rightHeaderContainer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  flex: 2;
}

.drawerBody {
  padding: 1rem;
  text-align: center;
}

```

### `src/components/rules_visualizer/RulesVisualizerHeader.tsx`

```typescript
import { useState } from 'react';
import { AutoComplete, Button, Drawer, Input, Space } from 'antd';
import { OptionData, OptionGroupData } from 'rc-select/lib/interface/index';
import { Core } from 'cytoscape';
import shallow from 'zustand/shallow';

import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import useRulesVisualizerStore from '../../stores/RulesVisualizerStore';
import { getGraphJson } from '../../actions/RulesVisualizerActions';
import Text, { TextSizes } from '../../uikit/Text';
import { DEFAULT_ANIMATE_DURATION } from './RulesVisualizer';
import { LabelInfo } from '../../stores/ApplicationConfigStore';

import styles from './RulesVisualizerHeader.module.css';

const RulesVisualizerHeader = ({
  cy,
  setIsLoading,
  showLabelUpstream,
  showLabelDownstream,
}: {
  cy: Core | null;
  setIsLoading: Function;
  showLabelUpstream: boolean;
  showLabelDownstream: boolean;
}) => {
  const [isDrawerVisible, setIsDrawerVisible] = useState(false);
  const [labelInfoMapping, knownActionNames] = useApplicationConfigStore(
    (state) => [state.labelInfoMapping, state.knownActionNames],
    shallow
  );
  const [updateRuleVizGraph, nodes, selectedFeature, selectedFeatureType] = useRulesVisualizerStore(
    (state) => [state.updateRuleVizGraph, state.nodes, state.selectedFeature, state.selectedFeatureType],
    shallow
  );

  const selectedFeatureText = (
    <Space>
      <Text size={TextSizes.H5}>{selectedFeatureType}</Text>
      <Text size={TextSizes.H7}>{selectedFeature}</Text>
    </Space>
  );

  const handleFeatureSelect = async (value: string, e: OptionData | OptionGroupData) => {
    setIsLoading(true);
    updateRuleVizGraph({ nodes: null, edges: null });
    const graphJson = await getGraphJson(e.type, [`${e.value}`], showLabelUpstream, showLabelDownstream);
    updateRuleVizGraph(graphJson);
    setIsLoading(false);
  };

  const handleNodeSelect = (value: string, e: OptionData | OptionGroupData) => {
    if (cy) {
      cy.animate({
        easing: 'ease-out-cubic',
        duration: DEFAULT_ANIMATE_DURATION,
        fit: { eles: cy.elements(), padding: 0 },
        complete: () => {
          cy.animate({
            easing: 'ease-in-cubic',
            duration: DEFAULT_ANIMATE_DURATION,
            fit: { eles: cy.getElementById(e.id), padding: 300 },
          });
        },
      });
    }
    setIsDrawerVisible(false);
  };

  const drawer = (
    <Drawer
      title={selectedFeatureText}
      placement="right"
      closable={false}
      onClose={() => setIsDrawerVisible(false)}
      open={isDrawerVisible}
      width="600"
    >
      <div className={styles.drawerBody}>
        <AutoComplete
          className={styles.autocomplete}
          options={nodes?.map((node) => ({ value: node.name, id: node.id }))}
          onSelect={handleNodeSelect}
          filterOption
        >
          <Input.Search size="large" placeholder="Search by node" enterButton allowClear />
        </AutoComplete>
      </div>
    </Drawer>
  );

  return (
    <div className={styles.header}>
      <Text className={styles.leftHeaderContainer} size={TextSizes.H3}>
        Rules Visualizer
      </Text>
      <div className={styles.rightHeaderContainer}>
        <Space>
          {selectedFeature && (
            <Button size="large" onClick={() => setIsDrawerVisible(true)}>
              {selectedFeatureText}
            </Button>
          )}
          <AutoComplete
            className={styles.autocomplete}
            options={getSuggestions(knownActionNames, labelInfoMapping)}
            onSelect={handleFeatureSelect}
            filterOption
            defaultOpen
            autoFocus
          >
            <Input.Search size="large" placeholder="Search by action or label" enterButton allowClear />
          </AutoComplete>
        </Space>
      </div>
      {drawer}
    </div>
  );
};

function getSuggestions(actions: Set<String>, labels: Map<string, LabelInfo>) {
  return [
    {
      label: 'Actions',
      options: [...actions].map((action) => ({
        value: action,
        type: 'action',
      })),
    },
    {
      label: 'Labels',
      options: [...labels.keys()].map((label) => ({
        value: label,
        type: 'label',
      })) as OptionData[],
    },
  ] as OptionGroupData[];
}

export default RulesVisualizerHeader;

```

### `src/components/saved_queries/DeleteSavedQueryModal.tsx`

```typescript
import * as React from 'react';
import { Modal } from 'antd';

import { deleteSavedQuery } from '../../actions/SavedQueryActions';
import useSavedQueryStore from '../../stores/SavedQueryStore';
import { SavedQuery } from '../../types/QueryTypes';
import Text, { TextSizes, TextWeights } from '../../uikit/Text';
import ModalFooter from '../common/ModalFooter';

interface DeleteSavedQueryModalProps {
  savedQuery: SavedQuery;
  onCancel: () => void;
}

const DeleteSavedQueryModal = ({ savedQuery, onCancel }: DeleteSavedQueryModalProps) => {
  const { savedQueries, updateSavedQueries } = useSavedQueryStore();
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const handleDeleteSavedQuery = async () => {
    setIsSubmitting(true);
    await deleteSavedQuery(savedQuery.id);

    const newSavedQueries = savedQueries.filter((query) => query.id !== savedQuery.id);
    updateSavedQueries(newSavedQueries);
    setIsSubmitting(false);

    onCancel();
  };

  return (
    <Modal
      title={<Text size={TextSizes.H5}>Deleting: {savedQuery.name}</Text>}
      footer={<ModalFooter onOK={handleDeleteSavedQuery} onCancel={onCancel} isSubmitting={isSubmitting} />}
      open
    >
      <Text tag="span" weight={TextWeights.BOLD}>
        Hey! Listen!
      </Text>{' '}
      Deleting this saved query is permanent and global, please be sure you have the right one before pressing OK.
    </Modal>
  );
};

export default DeleteSavedQueryModal;

```

### `src/components/saved_queries/EditSavedQueryNameModal.tsx`

```typescript
import * as React from 'react';
import { Modal, Form, Input } from 'antd';

import { updateSavedQuery } from '../../actions/SavedQueryActions';
import { SavedQuery } from '../../types/QueryTypes';
import Text, { TextSizes } from '../../uikit/Text';
import ModalFooter from '../common/ModalFooter';

interface EditSavedQueryNameModalProps {
  savedQuery: SavedQuery;
  onClose: () => void;
  onUpdate: (savedQuery: SavedQuery) => void;
}

const EditSavedQueryNameModal = ({ savedQuery, onClose, onUpdate }: EditSavedQueryNameModalProps) => {
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [updatedName, setUpdatedName] = React.useState(savedQuery.name);

  const handleValuesChange = (changedValues: { [key: string]: string }) => {
    setUpdatedName(changedValues.name);
  };

  const handleUpdateQueryName = async () => {
    setIsSubmitting(true);
    const updatedSavedQuery = await updateSavedQuery(savedQuery.id, updatedName);
    setIsSubmitting(false);
    onUpdate(updatedSavedQuery);
    onClose();
  };

  return (
    <Modal
      onCancel={onClose}
      title={<Text size={TextSizes.H5}>Editing Query: {savedQuery.name}</Text>}
      footer={
        <ModalFooter
          isDisabled={updatedName === savedQuery.name}
          onOK={handleUpdateQueryName}
          onCancel={onClose}
          isSubmitting={isSubmitting}
        />
      }
      open
    >
      <Form onValuesChange={handleValuesChange} onFinish={handleUpdateQueryName} layout="vertical">
        <Form.Item
          initialValue={savedQuery.name}
          label="New Name"
          name="name"
          rules={[{ required: true, message: 'Please enter new name for this query' }]}
        >
          <Input />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default EditSavedQueryNameModal;

```

### `src/components/saved_queries/SaveQueryModal.tsx`

```typescript
import * as React from 'react';
import { Modal, Form, Input } from 'antd';

import { createSavedQuery } from '../../actions/SavedQueryActions';
import useSavedQueryStore from '../../stores/SavedQueryStore';
import Text, { TextSizes } from '../../uikit/Text';
import ModalFooter from '../common/ModalFooter';

interface SaveQueryModalProps {
  queryId: string;
  onCancel: () => void;
}

const SaveQueryModal = ({ queryId, onCancel }: SaveQueryModalProps) => {
  const { savedQueries, updateSavedQueries } = useSavedQueryStore();
  const [form] = Form.useForm();

  const handleSaveQuery = async () => {
    const name = form.getFieldValue('name');
    const newSavedQuery = await createSavedQuery(queryId, name);

    updateSavedQueries([newSavedQuery, ...savedQueries]);
    onCancel();
  };

  return (
    <Modal
      title={<Text size={TextSizes.H5}>Save Query</Text>}
      onCancel={onCancel}
      footer={<ModalFooter onOK={handleSaveQuery} onCancel={onCancel} />}
      open
    >
      <Form form={form} onFinish={handleSaveQuery} layout="vertical">
        <Form.Item label="Name" name="name" rules={[{ required: true, message: 'Please name this query' }]}>
          <Input />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default SaveQueryModal;

```

### `src/components/saved_queries/SavedQueries.module.css`

```css
.viewContainer {
  height: 100%;
  width: 100%;
  max-height: calc(100vh - 42px);
  background-color: var(--background-primary);
  display: flex;
  overflow: hidden;
}

.header {
  padding: 14px;
  border-bottom: 1px var(--divider) solid;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}

.savedQueriesContainer {
  width: 900px;
  height: 100%;
  margin: 0 auto;
  border-left: 1px solid var(--divider);
  border-right: 1px solid var(--divider);
  display: flex;
  flex-direction: column;
}

```

### `src/components/saved_queries/SavedQueries.tsx`

```typescript
import * as React from 'react';

import { getSavedQueryUserEmails } from '../../actions/SavedQueryActions';
import { TextSizes } from '../../uikit/Text';
import SavedQueriesIcon from '../../uikit/icons/SavedQueriesIcon';
import IconHeader from '../common/IconHeader';
import UserSelect from '../common/UserSelect';
import { SavedQueryCardTypes } from './SavedQueryCard';
import SavedQueryList from './SavedQueryList';

import styles from './SavedQueries.module.css';

const SavedQueries = () => {
  const [userEmail, setUserEmail] = React.useState<string | undefined>();

  return (
    <div className={styles.viewContainer}>
      <div className={styles.savedQueriesContainer}>
        <div className={styles.header}>
          <IconHeader icon={<SavedQueriesIcon />} title="Saved Queries" size={TextSizes.H4} />
          <div>
            <UserSelect onSelect={setUserEmail} userResolver={getSavedQueryUserEmails} />
          </div>
        </div>
        <SavedQueryList userEmail={userEmail} cardType={SavedQueryCardTypes.DETAILED} />
      </div>
    </div>
  );
};

export default SavedQueries;

```

### `src/components/saved_queries/SavedQueryBar.module.css`

```css
.savedQueryBar {
  height: 40px;
  width: 100%;
  background-color: var(--background-primary);
  padding: 8px 16px;
  border-bottom: 1px solid var(--divider);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.editIcon {
  opacity: 0;
  margin-left: 6px;
  transition: 0.25s ease all;
}

.savedQueryName:hover .editIcon {
  opacity: 1;
  cursor: pointer;
}

```

### `src/components/saved_queries/SavedQueryBar.tsx`

```typescript
import * as React from 'react';
import { EditOutlined } from '@ant-design/icons';
import { message } from 'antd';
import { matchPath, useLocation, useParams } from 'react-router-dom';

import { getSavedQuery, updateSavedQuery } from '../../actions/SavedQueryActions';
import usePromiseResult from '../../hooks/usePromiseResult';
import useQueryStore, { history } from '../../stores/QueryStore';
import useSavedQueryStore from '../../stores/SavedQueryStore';
import { SavedQuery, TopNTable } from '../../types/QueryTypes';
import OspreyButton, { ButtonColors } from '../../uikit/OspreyButton';
import Text, { TextColors, TextWeights } from '../../uikit/Text';
import { getIntervalFromDateRange } from '../../utils/DateUtils';
import { renderFromPromiseResult } from '../../utils/PromiseResultUtils';
import { queryStateEquals } from '../../utils/QueryUtils';
import { makeSavedQueryRoute } from '../../utils/RouteUtils';
import { getSearchParamsForQueryRecord } from '../../utils/SearchParamUtils';
import EditSavedQueryNameModal from './EditSavedQueryNameModal';

import { Routes } from '../../Constants';
import styles from './SavedQueryBar.module.css';

const SavedQueryBarContent = ({ initialSavedQuery }: { initialSavedQuery: SavedQuery }) => {
  const executedQuery = useQueryStore((state) => state.executedQuery);
  const topNTables = useQueryStore((state) => state.topNTables);
  const charts = useQueryStore((state) => state.charts);
  const sortOrder = useQueryStore((state) => state.sortOrder);

  const { savedQueries, updateSavedQueries } = useSavedQueryStore();

  const [savedQuery, setSavedQuery] = React.useState(initialSavedQuery);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [showEditModal, setShowEditModal] = React.useState(false);

  const updateSavedQueryState = (updatedSavedQuery: SavedQuery) => {
    setSavedQuery(updatedSavedQuery);

    const storedQuery = savedQueries.find((query) => query.id === savedQuery.id);
    if (storedQuery != null) {
      const updatedSavedQueries = savedQueries.map((query) => (query.id === savedQuery.id ? updatedSavedQuery : query));
      updateSavedQueries(updatedSavedQueries);
    }
  };

  const handleUpdateSavedQuery = async () => {
    setIsSubmitting(true);
    const updatedSavedQuery = await updateSavedQuery(savedQuery.id, savedQuery.name, {
      executedQuery,
      topNTables,
      sortOrder,
      charts,
    });

    setIsSubmitting(false);
    updateSavedQueryState(updatedSavedQuery);

    message.success('Saved query updated', 1);
  };

  const renderUpdateOption = () => {
    const { query } = savedQuery;
    const queryState = { executedQuery, topNTables, sortOrder, charts };

    const savedQueryStateTablesMap: Map<string, TopNTable> = new Map();
    query.top_n.forEach((table) => savedQueryStateTablesMap.set(table.dimension, table));
    const savedQueryState = {
      executedQuery: {
        interval: getIntervalFromDateRange(query.date_range),
        start: query.date_range.start,
        end: query.date_range.end,
        queryFilter: query.query_filter,
      },
      topNTables: savedQueryStateTablesMap,
      sortOrder: query.sort_order,
      charts: [],
    };

    if (!queryStateEquals(queryState, savedQueryState)) {
      return (
        <OspreyButton loading={isSubmitting} color={ButtonColors.LINK_GRAY} onClick={handleUpdateSavedQuery}>
          Update saved query
        </OspreyButton>
      );
    }

    return null;
  };

  const handleToggleEditNameModal = () => {
    setShowEditModal(!showEditModal);
  };

  return (
    <>
      <div>
        <Text tag="span" color={TextColors.LIGHT_SECONDARY}>
          Viewing saved query
        </Text>{' '}
        <Text
          tag="span"
          className={styles.savedQueryName}
          color={TextColors.LIGHT_HEADINGS_PRIMARY}
          weight={TextWeights.SEMIBOLD}
        >
          {savedQuery.name}
          <EditOutlined className={styles.editIcon} onClick={handleToggleEditNameModal} />
        </Text>
      </div>
      {renderUpdateOption()}
      {showEditModal ? (
        <EditSavedQueryNameModal
          savedQuery={savedQuery}
          onClose={handleToggleEditNameModal}
          onUpdate={updateSavedQueryState}
        />
      ) : null}
    </>
  );
};

const SavedQueryBar = () => {
  const { savedQueryId } = useParams<{ savedQueryId: string }>();
  const location = useLocation();

  const savedQueryResults = usePromiseResult(async () => {
    const savedQuery = await getSavedQuery(savedQueryId);
    const useInterval = matchPath(location.pathname, { path: Routes.SAVED_QUERY_LATEST }) != null;

    history.replace({
      pathname: makeSavedQueryRoute(savedQuery),
      search: getSearchParamsForQueryRecord(savedQuery.query, useInterval),
    });

    return savedQuery;
  }, [savedQueryId]);

  return (
    <div className={styles.savedQueryBar}>
      {renderFromPromiseResult(
        savedQueryResults,
        (savedQuery) => (
          <SavedQueryBarContent initialSavedQuery={savedQuery} />
        ),
        { renderResolving: () => <div>Fetching saved query data...</div> }
      )}
    </div>
  );
};

export default SavedQueryBar;

```

### `src/components/saved_queries/SavedQueryCard.module.css`

```css
.queryCard {
  width: 100%;
  border-bottom: 1px var(--divider) solid;
}

.titleRow {
  display: flex;
  justify-content: space-between;
  flex-grow: 1;
}

.savedQueryActionData {
  padding: 4px 16px 8px;
  background-color: var(--background-secondary-alt);
}

.savedQueryCardCompact {
  padding: 8px;
  border-bottom: 1px solid var(--divider);
  display: flex;
  flex-direction: column;
}

.detailsRow {
  margin-top: 8px;
}

.savedQueryCardButtons {
  width: 100%;
  display: flex;
  padding: 8px 16px;
}

```

### `src/components/saved_queries/SavedQueryCard.tsx`

```typescript
import * as React from 'react';
import dayjs from 'dayjs';

import { SavedQuery, IntervalOptions, MomentRangeValues, QueryRecord } from '../../types/QueryTypes';
import { MenuOption } from '../../uikit/DropdownMenu';
import { ExpandContextProvider } from '../../uikit/Expand';
import Text, { TextWeights } from '../../uikit/Text';
import { getIntervalFromDateRange, localizeAndFormatTimestamp } from '../../utils/DateUtils';
import IconDropdownMenu from '../common/IconDropdownMenu';
import { QueryCardBody, QueryCardActionData, QueryCardHeader } from '../common/QueryCards';
import SavedQueryCardButtons from './SavedQueryCardButtons';

import styles from './SavedQueryCard.module.css';
import { querySearchContext } from '../query_view/QuerySearchContext';
import { highlightMatchedText, splitStringIncludingMatches } from '../../utils/StringUtils';

export enum SavedQueryActions {
  SHOW_HISTORY,
  DELETE,
  RUN_ORIGINAL,
  RUN_INTERVAL,
}

export enum SavedQueryCardTypes {
  COMPACT,
  DETAILED,
  VERSION_HISTORY,
}

const SavedQueryMenuOptions = [
  { label: 'Run Original Query', action: SavedQueryActions.RUN_ORIGINAL },
  { label: 'Run Query Using Interval', action: SavedQueryActions.RUN_INTERVAL },
  { label: 'Show Saved Query History', action: SavedQueryActions.SHOW_HISTORY },
  { label: 'Delete Saved Query', action: SavedQueryActions.DELETE },
];

interface SavedQueryCardProps {
  savedQuery: SavedQuery;
  query?: QueryRecord;
  isCompact?: boolean;
  onMenuItemClick?: (savedQuery: SavedQuery, action: SavedQueryActions) => void;
  type?: SavedQueryCardTypes;
}

const SavedQueryCard = ({
  savedQuery,
  query,
  onMenuItemClick,
  type = SavedQueryCardTypes.DETAILED,
}: SavedQueryCardProps) => {
  const searchQuery = React.useContext(querySearchContext);

  const queryRecord = query == null ? savedQuery.query : query;
  const interval = getIntervalFromDateRange(queryRecord.date_range);
  const intervalCopy = interval == null ? '' : IntervalOptions[interval as MomentRangeValues].label;

  const handleMenuItemClick = (action: SavedQueryActions) => {
    onMenuItemClick?.(savedQuery, action);
  };

  const getDropdownMenuOptions = (): MenuOption[] =>
    SavedQueryMenuOptions.filter(
      // If the saved query has no interval (i.e. it's a custom range), do not render the 'Run Interval' option.
      (option) => !(option.action === SavedQueryActions.RUN_INTERVAL && interval == null)
    ).map((option) => ({
      label: option.label,
      onClick: () => handleMenuItemClick(option.action),
    }));

  const highlightedHeaderContent = highlightMatchedText(
    splitStringIncludingMatches(savedQuery.name, searchQuery.query, searchQuery.regex)
  );
  const headerContent = (
    <div className={styles.titleRow}>
      <Text weight={TextWeights.SEMIBOLD}>{highlightedHeaderContent}</Text>
      <IconDropdownMenu options={getDropdownMenuOptions()} />
    </div>
  );

  const highlightedQueryContent = highlightMatchedText(
    splitStringIncludingMatches(savedQuery.query.query_filter, searchQuery.query, searchQuery.regex)
  );

  const actionData = (
    <div className={styles.savedQueryActionData}>
      <QueryCardActionData user={savedQuery.saved_by} timestamp={savedQuery.saved_at} action="saved at" />
    </div>
  );

  switch (type) {
    case SavedQueryCardTypes.COMPACT:
      return (
        <div className={styles.savedQueryCardCompact}>
          {headerContent}
          <div className={styles.detailsRow}>
            <QueryCardActionData user={savedQuery.saved_by} action="•" timestamp={savedQuery.saved_at} />
          </div>
        </div>
      );
    case SavedQueryCardTypes.VERSION_HISTORY:
      return (
        <ExpandContextProvider>
          <div className={styles.queryCard}>
            <QueryCardHeader>
              <div className={styles.titleRow}>
                <Text weight={TextWeights.SEMIBOLD}>{`Version saved at: ${localizeAndFormatTimestamp(
                  dayjs.unix(queryRecord.executed_at)
                )}`}</Text>
              </div>
            </QueryCardHeader>
            <QueryCardBody query={queryRecord} intervalCopy={intervalCopy} />
            {actionData}
          </div>
        </ExpandContextProvider>
      );
    case SavedQueryCardTypes.DETAILED:
      return (
        <ExpandContextProvider>
          <div className={styles.queryCard}>
            <QueryCardHeader>{headerContent}</QueryCardHeader>
            <QueryCardBody query={queryRecord} intervalCopy={intervalCopy} />
            {actionData}
            <SavedQueryCardButtons savedQuery={savedQuery} interval={interval} intervalCopy={intervalCopy} />
          </div>
        </ExpandContextProvider>
      );
  }
};

export default SavedQueryCard;

```

### `src/components/saved_queries/SavedQueryCardButtons.module.css`

```css
.savedQueryCardButtons {
  width: 100%;
  display: flex;
  padding: 8px 16px;
}

.originalQueryButton {
  margin-right: 16px;
}

```

### `src/components/saved_queries/SavedQueryCardButtons.tsx`

```typescript
import * as React from 'react';
import { Link } from 'react-router-dom';

import { SavedQuery, MomentRangeValues } from '../../types/QueryTypes';
import OspreyButton from '../../uikit/OspreyButton';
import { makeLatestSavedQueryRoute, makeSavedQueryRoute } from '../../utils/RouteUtils';

import styles from './SavedQueryCardButtons.module.css';

const SavedQueryCardButtons = ({
  savedQuery,
  interval,
  intervalCopy,
}: {
  savedQuery: SavedQuery;
  interval: MomentRangeValues | null;
  intervalCopy: string;
}) => {
  const renderQueryIntervalButton = () => {
    if (interval == null) return null;

    return (
      <OspreyButton>
        <Link to={{ pathname: makeLatestSavedQueryRoute(savedQuery) }}>Query {intervalCopy}</Link>
      </OspreyButton>
    );
  };

  return (
    <div className={styles.savedQueryCardButtons}>
      <OspreyButton className={styles.originalQueryButton}>
        <Link to={{ pathname: makeSavedQueryRoute(savedQuery) }}>View Original Query</Link>
      </OspreyButton>
      {renderQueryIntervalButton()}
    </div>
  );
};

export default SavedQueryCardButtons;

```

### `src/components/saved_queries/SavedQueryDrawer.module.css`

```css
.queryDrawerHeader {
  padding: 16px;
  border-bottom: 1px solid var(--divider);
}

```

### `src/components/saved_queries/SavedQueryDrawer.tsx`

```typescript
import * as React from 'react';
import { Drawer } from 'antd';

import { getSavedQueryHistory } from '../../actions/SavedQueryActions';
import usePromiseResult from '../../hooks/usePromiseResult';
import { SavedQuery } from '../../types/QueryTypes';
import Text, { TextSizes } from '../../uikit/Text';
import { renderFromPromiseResult } from '../../utils/PromiseResultUtils';
import SavedQueryCard, { SavedQueryCardTypes } from './SavedQueryCard';

import styles from './SavedQueryDrawer.module.css';

interface SavedQueryDrawerProps {
  savedQuery: SavedQuery | null;
  onClose: () => void;
}

const SavedQueryDrawerContent = ({ savedQuery }: { savedQuery: SavedQuery }) => {
  const savedQueryHistoryResults = usePromiseResult(() => getSavedQueryHistory(savedQuery.id));

  return renderFromPromiseResult(savedQueryHistoryResults, (savedQueryHistory) => {
    const renderQueryHistoryList = () => {
      if (savedQueryHistory.length === 0) {
        return <Text size={TextSizes.H7}>No version history</Text>;
      }

      return savedQueryHistory.map((query) => (
        <SavedQueryCard
          key={query.id}
          savedQuery={savedQuery}
          query={query}
          type={SavedQueryCardTypes.VERSION_HISTORY}
        />
      ));
    };

    return (
      <>
        <Text className={styles.queryDrawerHeader} size={TextSizes.H4}>
          Version History: {savedQuery.name}
        </Text>
        <div>{renderQueryHistoryList()}</div>
      </>
    );
  });
};

const SavedQueryDrawer = ({ savedQuery, onClose }: SavedQueryDrawerProps) => {
  const renderDrawerContent = () => {
    if (savedQuery == null) return null;
    return <SavedQueryDrawerContent savedQuery={savedQuery} />;
  };

  return (
    <Drawer placement="right" width={750} open={savedQuery != null} closable={false} onClose={onClose} destroyOnClose>
      {renderDrawerContent()}
    </Drawer>
  );
};

export default SavedQueryDrawer;

```

### `src/components/saved_queries/SavedQueryList.module.css`

```css
.listContainer {
  overflow-y: auto;
  max-height: 100%;
  flex-grow: 1;
  overflow-anchor: none;
}

```

### `src/components/saved_queries/SavedQueryList.tsx`

```typescript
import * as React from 'react';
import InfiniteScroll from 'react-infinite-scroller';
import { Redirect } from 'react-router-dom';

import { getSavedQueries } from '../../actions/SavedQueryActions';
import usePromiseResult from '../../hooks/usePromiseResult';
import useSavedQueryStore from '../../stores/SavedQueryStore';
import { SavedQuery } from '../../types/QueryTypes';
import { renderFromPromiseResult } from '../../utils/PromiseResultUtils';
import { makeLatestSavedQueryRoute, makeSavedQueryRoute } from '../../utils/RouteUtils';
import { querySearchContext } from '../query_view/QuerySearchContext';
import DeleteSavedQueryModal from './DeleteSavedQueryModal';
import SavedQueryCard, { SavedQueryActions, SavedQueryCardTypes } from './SavedQueryCard';
import SavedQueryDrawer from './SavedQueryDrawer';

import styles from './SavedQueryList.module.css';
import { splitStringIncludingMatches } from '../../utils/StringUtils';

interface SavedQueryListProps {
  cardType: SavedQueryCardTypes;
  userEmail?: string;
}

const SavedQueryList = ({ cardType, userEmail }: SavedQueryListProps) => {
  const [selectedSavedQuery, setSelectedSavedQuery] = React.useState<SavedQuery | null>(null);
  const [action, setAction] = React.useState<SavedQueryActions | null>(null);
  const [hasMoreSavedQueries, setHasMoreSavedQueries] = React.useState(true);
  const { query: searchQuery, regex } = React.useContext(querySearchContext);

  const { savedQueries, updateSavedQueries } = useSavedQueryStore();

  const savedQueryResults = usePromiseResult(async () => {
    const fetchedSavedQueries = await getSavedQueries(userEmail);
    updateSavedQueries(fetchedSavedQueries);
  }, [userEmail]);

  const handleClearState = () => {
    setSelectedSavedQuery(null);
    setAction(null);
  };

  const setQueryAction = (savedQuery: SavedQuery, action: SavedQueryActions) => {
    setSelectedSavedQuery(savedQuery);
    setAction(action);
  };

  const renderFromAction = () => {
    if (selectedSavedQuery == null) return null;

    switch (action) {
      case SavedQueryActions.RUN_ORIGINAL:
        return <Redirect push to={{ pathname: makeSavedQueryRoute(selectedSavedQuery) }} />;
      case SavedQueryActions.RUN_INTERVAL:
        return <Redirect push to={{ pathname: makeLatestSavedQueryRoute(selectedSavedQuery) }} />;
      case SavedQueryActions.DELETE:
        return <DeleteSavedQueryModal savedQuery={selectedSavedQuery} onCancel={handleClearState} />;
      case SavedQueryActions.SHOW_HISTORY:
        return <SavedQueryDrawer savedQuery={selectedSavedQuery} onClose={handleClearState} />;
      default:
        return null;
    }
  };

  const loadMoreSavedQueries = async () => {
    const lastSavedQuery = savedQueries[savedQueries.length - 1];
    if (lastSavedQuery == null) {
      setHasMoreSavedQueries(false);
      return;
    }

    const newSavedQueries = await getSavedQueries(userEmail, lastSavedQuery.id);

    if (newSavedQueries.length === 0 || newSavedQueries.length % 100 !== 0) {
      setHasMoreSavedQueries(false);
    }

    updateSavedQueries([...savedQueries, ...newSavedQueries]);
  };

  const filterSavedQueries = (query: SavedQuery) => {
    if (!searchQuery || searchQuery === '') return true;
    const queryFilterMatches = splitStringIncludingMatches(query.query.query_filter, searchQuery, regex);
    if (queryFilterMatches.find((val) => val.matched)) return true;
    const queryNameMatches = splitStringIncludingMatches(query.name, searchQuery, regex);
    if (queryNameMatches.find((val) => val.matched)) return true;
    return false;
  };
  return (
    <>
      {renderFromPromiseResult(savedQueryResults, () => (
        <div className={styles.listContainer}>
          <InfiniteScroll pageStart={0} loadMore={loadMoreSavedQueries} hasMore={hasMoreSavedQueries} useWindow={false}>
            {savedQueries.filter(filterSavedQueries).map((savedQuery) => (
              <SavedQueryCard
                key={savedQuery.id}
                savedQuery={savedQuery}
                onMenuItemClick={setQueryAction}
                type={cardType}
              />
            ))}
          </InfiniteScroll>
        </div>
      ))}
      {renderFromAction()}
    </>
  );
};

export default SavedQueryList;

```

### `src/components/timeseries/Timeseries.module.css`

```css
.timeseriesPanel {
  display: flex;
  flex-direction: column;
  min-height: 200px;
}

.chartContainer {
  user-select: none;
}

.emptyChartOverlayContainer {
  position: relative;
}

.emptyChartOverlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;

  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--background-tertiary);
}

```

### `src/components/timeseries/Timeseries.tsx`

```typescript
import * as React from 'react';
import { Select, Spin } from 'antd';
import Highcharts, { SeriesOptionsType } from 'highcharts';
import HighchartsReact from 'highcharts-react-official';
import dayjs from 'dayjs';
import shallow from 'zustand/shallow';

import { getTimeseriesQueryResults } from '../../actions/EventActions';
import useQueryStore from '../../stores/QueryStore';
import { TimeseriesResult } from '../../types/QueryTypes';
import Text, { TextSizes } from '../../uikit/Text';
import TimeseriesIcon from '../../uikit/icons/TimeseriesIcon';
import Panel from '../common/Panel';

import styles from './Timeseries.module.css';
import { makeEntityRoute } from '../../utils/RouteUtils';

const CHART_TYPE = 'column';
// prettier-ignore
const Granularities = {
  // name: duration in ms
  minute: 1000 * 60,
  fifteen_minute: 1000 * 60 * 15,
  thirty_minute: 1000 * 60 * 30,
  hour: 1000 * 60 * 60,
  day: 1000 * 60 * 60 * 24,
  week: 1000 * 60 * 60 * 24 * 7,
  month: 1000 * 60 * 60 * 24 * 30,
};
const GRANULARITY_STRINGS = {
  minute: 'minute',
  fifteen_minute: 'fifteen minutes',
  thirty_minute: 'half hour',
  hour: 'hour',
  day: 'day',
  week: 'week',
  month: 'month',
};
const DEFAULT_GRANULARITY = 'hour';
type Granularity = keyof typeof Granularities;

function getDateFormatForGranularity(granularity: Granularity | 'other'): string {
  // https://api.highcharts.com/class-reference/Highcharts#.dateFormat
  switch (granularity) {
    case 'minute':
      // 4:23PM
      return '%l:%M%p';
    case 'fifteen_minute':
    case 'thirty_minute':
    case 'hour':
      // Jun 1 4PM
      return '%b %e %l%p';
    case 'day':
    case 'week':
      // Jun 1, 2020
      return '%b %e, %Y';
    case 'month':
      // Jun 2020
      return '%b %Y';
    default:
      // Jun 1, 2020 4:23PM
      return '%b %e, %Y %l:%M%p';
  }
}

const MIN_GRANULARITY_DATAPOINTS = 7;
function getDefaultGranularityForTimeSpan(start: string | null, end: string | null): Granularity {
  // choose the largest granularity that would have more than $MIN_GRANULARITY_DATAPOINTS datapoints
  // calculate duration, and from there, figure out

  if (!start || !end) {
    // we won't be able to determine duration
    return DEFAULT_GRANULARITY;
  }

  // ms difference between start and end dates
  const startDate = dayjs(start);
  const endDate = dayjs(end);
  const duration = Math.abs(dayjs.duration(endDate.diff(startDate)).asMilliseconds());

  // sort granularities by desc duration
  const sortedGranularities = (Object.entries(Granularities) as Array<[Granularity, number]>).sort(
    ([, durationA], [, durationB]) => durationB - durationA
  );

  let currentGranularity: Granularity | null = null;
  for (const [granularity, granularityDuration] of sortedGranularities) {
    currentGranularity = granularity;

    if (duration / granularityDuration > MIN_GRANULARITY_DATAPOINTS) {
      // this granularity meets our minimum data points
      break;
    }
  }

  if (currentGranularity == null) {
    throw new Error('Could not determine granularity for timespan!');
  }

  return currentGranularity;
}

function getChartData(timeseriesData: TimeseriesResult[]): SeriesOptionsType[] {
  if (timeseriesData.length <= 1) {
    return [];
  }

  const data = timeseriesData.map((point: TimeseriesResult) => [Date.parse(point.timestamp), point.result.count]);

  return [
    {
      type: CHART_TYPE,
      data: data,
      name: '# Events',
      color: '#8e5ea2',
      // By default, Highcarts groups multiple series for the same x together;
      // because we only have one data series, we don't want to have any padding between the lines.
      groupPadding: 0,
    },
  ];
}

const EmptyOverlay = ({ show, children }: { show: boolean; children: React.ReactNode }) => {
  const overlay = show ? (
    <Text size={TextSizes.LARGE} className={styles.emptyChartOverlay}>
      No data available
    </Text>
  ) : null;
  return (
    <div className={styles.emptyChartOverlayContainer}>
      {children}
      {overlay}
    </div>
  );
};

const GranularitySelect = ({
  onChange,
  granularity,
}: {
  onChange: (value: Granularity) => void;
  granularity: Granularity;
}): React.ReactElement => {
  return (
    <Select showSearch value={granularity} onChange={onChange} style={{ minWidth: 200 }}>
      {Object.keys(Granularities).map((option: string) => (
        <Select.Option key={option} value={option}>
          {GRANULARITY_STRINGS[option as Granularity]}
        </Select.Option>
      ))}
    </Select>
  );
};

interface TimeseriesProps {
  extraQuery?: string;
}

const Timeseries: React.FC<TimeseriesProps> = ({ extraQuery }: TimeseriesProps) => {
  const [executedQuery, entityFeatureFilters, applyIfQueryIsCurrent, updateExecutedQuery] = useQueryStore(
    (state) => [
      state.executedQuery,
      state.entityFeatureFilters,
      state.applyIfQueryIsCurrent,
      state.updateExecutedQuery,
    ],
    shallow
  );
  const { start, end } = executedQuery;

  const [timeseriesData, setTimeseriesData] = React.useState<TimeseriesResult[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [granularity, setGranularity] = React.useState(getDefaultGranularityForTimeSpan(start, end));

  React.useEffect(() => {
    setIsLoading(true);

    let shouldApply = true;
    async function getTimeseriesResults() {
      if (start !== '' && end !== '') {
        const query = { ...executedQuery };
        query.queryFilter = [extraQuery, executedQuery.queryFilter]
          .filter((q) => q !== undefined && q !== '')
          .map((q) => `(${q})`)
          .join(' and ');
        const results = await getTimeseriesQueryResults({ ...query, entityFeatureFilters }, granularity);
        // don't apply results if we triggered a new fetch
        if (!shouldApply) return;
        applyIfQueryIsCurrent(executedQuery, () => setTimeseriesData(results));
      }

      setIsLoading(false);
    }

    setTimeseriesData([]);
    getTimeseriesResults();

    return () => {
      // this means the component is either unmounting, or is about to run a new fetch
      shouldApply = false;
    };
  }, [granularity, executedQuery, applyIfQueryIsCurrent, start, end, entityFeatureFilters, extraQuery]);

  React.useEffect(() => {
    // update granularity when we change the query range
    setGranularity(getDefaultGranularityForTimeSpan(start, end));
  }, [start, end]);

  function handleChartSelection(event: Highcharts.ChartSelectionContextObject): false {
    const newRange = event.xAxis?.[0];
    if (newRange == null) return false;

    // Highcharts does not update the values of executedQuery when the component rerenders,
    // so get it directly from the store when handler is called.
    const { executedQuery } = useQueryStore.getState();

    updateExecutedQuery({
      ...executedQuery,
      interval: 'custom',
      start: new Date(newRange.min).toISOString(),
      end: new Date(newRange.max).toISOString(),
    });
    // return false because we don't want highcharts to apply the zoom, as we'll just re-query the data instead
    return false;
  }

  const chartData = getChartData(timeseriesData);
  const chartOptions: Highcharts.Options = {
    chart: {
      type: CHART_TYPE,
      height: 300,
      // allows selection of a subset of date
      zoomType: 'x',
      events: {
        // event handler for the selection
        selection: handleChartSelection,
      },
    },
    title: {
      text: undefined,
    },
    credits: {
      enabled: false,
    },
    xAxis: {
      type: 'datetime',
      // adjusts granularity of each tick
      tickPixelInterval: 10,
      labels: {
        format: `{value:${getDateFormatForGranularity(granularity)}}`,
        rotation: -45,
      },
      // shows x-axis grid
      gridLineWidth: 1,
      title: {
        text: undefined,
      },
    },
    yAxis: {
      type: 'linear',
      // always start at 0 events
      min: 0,
      tickPixelInterval: 10,
      labels: {
        format: '{value:,.0f}',
      },
      title: {
        text: undefined,
      },
    },
    tooltip: {
      // date format for tooltip's x value (in our case, datetime)
      xDateFormat: getDateFormatForGranularity('other'),
    },
    time: {
      // our time data is UTC, but we'll convert it to whatever timezone dayjs
      // thinks the user is in
      timezone: dayjs.tz.guess(),
      // don't render time as UTC
      useUTC: false,
    },
    legend: {
      enabled: false,
    },
    series: chartData,
  };

  return (
    <Panel
      className={styles.timeseriesPanel}
      title="Timeseries Chart"
      icon={<TimeseriesIcon />}
      titleRight={<GranularitySelect granularity={granularity} onChange={setGranularity} />}
    >
      <Spin spinning={isLoading}>
        <div className={styles.chartContainer}>
          <EmptyOverlay show={chartData.length === 0}>
            <HighchartsReact highcharts={Highcharts} options={chartOptions} />
          </EmptyOverlay>
        </div>
      </Spin>
    </Panel>
  );
};

export default Timeseries;

```

### `src/components/top_n/CSVDownloadModal.module.css`

```css
.csvButton {
  margin-left: 6px;
}

.warning {
  white-space: pre-line;
}

.radioOption {
  margin-bottom: 6px;
}

.limitInput {
  margin-top: 8px;
}

.footer {
  display: flex;
  justify-content: flex-end;
}

```

### `src/components/top_n/CSVDownloadModal.tsx`

```typescript
import * as React from 'react';
import { DownloadOutlined } from '@ant-design/icons';
import { Alert, Form, Input, Modal, Radio } from 'antd';
import { Store } from 'antd/lib/form/interface';
import { RadioChangeEvent } from 'antd/lib/radio';

import { getTopNQueryResultCSV } from '../../actions/EventActions';
import useQueryStore from '../../stores/QueryStore';
import OspreyButton, { ButtonColors } from '../../uikit/OspreyButton';
import Text, { TextSizes } from '../../uikit/Text';

import styles from './CSVDownloadModal.module.css';

interface CSVDownloadModalProps {
  disabled: boolean;
  dimension: string;
}

enum RadioOptions {
  MAXIMUM,
  CUSTOM,
}

const MAXIMUM_ROWS = 100000;

function validateLimitInput(_: any, limitStr: string): Promise<void> {
  const limit = Number(limitStr);

  if (isNaN(limit) || limit <= 0) {
    return Promise.reject('Invalid number'); /* eslint-disable-line */
  } else if (limit > MAXIMUM_ROWS) {
    return Promise.reject('Maximum 100,000 rows allowed per CSV'); /* eslint-disable-line */
  }

  return Promise.resolve();
}

const CSVDownloadModal = ({ disabled, dimension }: CSVDownloadModalProps) => {
  const [isCSVDownloading, setIsCSVDownloading] = React.useState(false);
  const [isModalOpen, setIsModalOpen] = React.useState(false);
  const [limitOption, setLimitOption] = React.useState(RadioOptions.MAXIMUM);

  const executedQuery = useQueryStore((state) => state.executedQuery);
  const entityFeatureFilters = useQueryStore((state) => state.entityFeatureFilters);
  const [form] = Form.useForm();

  const handleDownload = async (values?: Store) => {
    const maybeLimit = Number(values?.limit);
    const limit = isNaN(maybeLimit) ? MAXIMUM_ROWS : maybeLimit;

    setIsCSVDownloading(true);
    setIsModalOpen(false);
    await getTopNQueryResultCSV({ ...executedQuery, entityFeatureFilters }, dimension, limit);
    setIsCSVDownloading(false);

    form.resetFields();
    setLimitOption(RadioOptions.MAXIMUM);
  };

  const handleRadioClick = (e: RadioChangeEvent) => {
    setLimitOption(e.target.value);
  };

  const renderLimitForm = () => {
    return (
      <Form form={form} onFinish={handleDownload}>
        <Form.Item name="limit" rules={[{ required: true }, { validator: validateLimitInput }]} validateFirst>
          <Input className={styles.limitInput} placeholder="Number of rows (maximum 100,000)" />
        </Form.Item>
      </Form>
    );
  };

  return (
    <>
      <OspreyButton
        color={ButtonColors.LINK_GRAY}
        onClick={() => setIsModalOpen(true)}
        disabled={disabled}
        loading={isCSVDownloading}
        key="download"
      >
        <DownloadOutlined />
        Download CSV
      </OspreyButton>
      <Modal
        title={<Text size={TextSizes.H5}>Download CSV</Text>}
        width={400}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={
          <div className={styles.footer}>
            <OspreyButton key="cancel" onClick={() => setIsModalOpen(false)}>
              Cancel
            </OspreyButton>
            <OspreyButton
              key="ok"
              color={ButtonColors.DARK_BLUE}
              onClick={limitOption === RadioOptions.CUSTOM ? form.submit : handleDownload}
            >
              OK
            </OspreyButton>
          </div>
        }
      >
        <Alert
          style={{ marginBottom: 12 }}
          message="Large CSV downloads can take several minutes."
          type="warning"
          showIcon
        />
        <Radio.Group value={limitOption} onChange={handleRadioClick}>
          <Radio className={styles.radioOption} value={RadioOptions.MAXIMUM}>
            Download Maximum Rows (up to 100,000)
          </Radio>
          <Radio className={styles.radioOption} value={RadioOptions.CUSTOM}>
            Set Row Limit
          </Radio>
        </Radio.Group>
        {limitOption === RadioOptions.CUSTOM ? renderLimitForm() : null}
      </Modal>
    </>
  );
};

export default CSVDownloadModal;

```

### `src/components/top_n/FeatureNameSelect.tsx`

```typescript
import * as React from 'react';
import { Select } from 'antd';
import shallow from 'zustand/shallow';

import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import useQueryStore from '../../stores/QueryStore';
import { isEmptyDateRange } from '../../utils/QueryUtils';
import OptionLabelWithInfo from '../common/OptionLabelWithInfo';
import { filterAutoComplete, sortOptions } from '../../utils/AutoCompleteUtils';

const FeatureNameSelect = React.memo(
  ({
    selectedFeatureName,
    onFeatureNameChange,
  }: {
    selectedFeatureName: string;
    onFeatureNameChange: (val: string) => void;
  }): React.ReactElement => {
    const [executedQuery, topNTables] = useQueryStore((state) => [state.executedQuery, state.topNTables], shallow);
    const [knownFeatureNames, ruleInfoMapping] = useApplicationConfigStore((state) => [
      state.knownFeatureNames,
      state.ruleInfoMapping,
    ]);

    const options = [...knownFeatureNames]
      .filter((featureName) => !topNTables.has(featureName))
      .map((option: string) => ({
        value: option,
        label: <OptionLabelWithInfo option={option} optionInfoMapping={ruleInfoMapping} />,
      }));

    const [filteredOptions, setFilteredOptions] = React.useState(options);

    const handleSearch = (inputValue: string) => {
      const sortedOptions = options
        .filter((option) => filterAutoComplete(inputValue, option))
        .sort(sortOptions(inputValue));

      setFilteredOptions(sortedOptions);
    };

    return (
      <Select
        showSearch
        placeholder="Select Feature Name"
        value={selectedFeatureName}
        onChange={onFeatureNameChange}
        onSearch={(inputText) => {
          handleSearch(inputText);
        }}
        style={{ width: '100%' }}
        disabled={isEmptyDateRange(executedQuery.start, executedQuery.end)}
        filterOption={false}
        options={filteredOptions}
      />
    );
  }
);

export default FeatureNameSelect;

```

### `src/components/top_n/TopN.module.css`

```css
.tableWrapper {
  padding-top: 8px;
}

.topNPanel {
  flex-grow: 1;
  border-top: 2px solid var(--divider);
}

```

### `src/components/top_n/TopN.tsx`

```typescript
import * as React from 'react';
import { Empty } from 'antd';

import useQueryStore from '../../stores/QueryStore';
import { TopNTable } from '../../types/QueryTypes';
import OspreyButton from '../../uikit/OspreyButton';
import TopNIcon from '../../uikit/icons/TopNIcon';
import Panel from '../common/Panel';
import Table from './TopNTable';

import styles from './TopN.module.css';

const TopN: React.FC = () => {
  const [hasEmptyTable, setHasEmptyTable] = React.useState(false);
  const [topNTables, updateTopNTables] = useQueryStore((state) => [state.topNTables, state.updateTopNTables]);

  const handleAddTable = () => {
    setHasEmptyTable(true);
  };

  const handleRemoveTable = (dimension: string) => {
    if (dimension === '') {
      setHasEmptyTable(false);
      return;
    }

    const updatedTables: Map<string, TopNTable> = new Map(topNTables);
    updatedTables.delete(dimension);
    updateTopNTables(updatedTables);
  };

  const handleUpdateDimension = (oldDimension: string, newDimension: string) => {
    const updatedTables: Map<string, TopNTable> = new Map();
    // Maps retain ordering based on insertion; We are basing our insertion ordering off of that fact
    if (oldDimension === '') {
      setHasEmptyTable(false);
      updatedTables.set(newDimension, new TopNTable(newDimension));
    }
    topNTables.forEach((table, dimension) => {
      if (dimension === oldDimension) {
        updatedTables.set(newDimension, new TopNTable(newDimension));
      } else {
        updatedTables.set(dimension, table);
      }
    });

    updateTopNTables(updatedTables);
  };

  const handleUpdatePrecision = (dimension: string, newPrecision: number) => {
    const updatedTables: Map<string, TopNTable> = new Map(topNTables);
    if (updatedTables.has(dimension)) {
      updatedTables.get(dimension)!.precision = newPrecision;
      updateTopNTables(updatedTables);
    }
  };

  const handleTogglePoP = (dimension: string) => {
    const updatedTables: Map<string, TopNTable> = new Map(topNTables);
    if (updatedTables.has(dimension)) {
      const currentTable = updatedTables.get(dimension);
      if (currentTable) {
        currentTable.isPoPEnabled = !currentTable.isPoPEnabled;
        updateTopNTables(updatedTables);
      }
    }
  };

  const renderTopNTables = () => {
    if (topNTables.size === 0 && !hasEmptyTable) {
      return <Empty style={{ paddingTop: 40 }} />;
    }

    const tablesToRender = [...topNTables.values()];

    if (hasEmptyTable) {
      tablesToRender.unshift(new TopNTable(''));
    }

    return (
      <div className={styles.tableWrapper}>
        {tablesToRender.map((table: TopNTable) => {
          return (
            <Table
              key={table.dimension}
              dimension={table.dimension}
              precision={table.precision}
              showPrecision={table.showPrecision}
              isPoPEnabled={table.isPoPEnabled}
              onRemoveTable={handleRemoveTable}
              onDimensionChange={handleUpdateDimension}
              onPrecisionChange={handleUpdatePrecision}
              onTogglePoP={handleTogglePoP}
            />
          );
        })}
      </div>
    );
  };

  return (
    <Panel
      className={styles.topNPanel}
      title="Top N Results"
      icon={<TopNIcon />}
      titleRight={
        <OspreyButton disabled={hasEmptyTable} onClick={handleAddTable}>
          Add Table
        </OspreyButton>
      }
    >
      {renderTopNTables()}
    </Panel>
  );
};

export default TopN;

```

### `src/components/top_n/TopNFooter.module.css`

```css
.menu {
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 2px 0;
}

```

### `src/components/top_n/TopNFooter.tsx`

```typescript
import * as React from 'react';
import { SelectOutlined, StopOutlined } from '@ant-design/icons';

import useApplicationConfigStore from '../../stores/ApplicationConfigStore';
import useLabelStore from '../../stores/LabelStore';
import OspreyButton, { ButtonColors } from '../../uikit/OspreyButton';
import CSVDownloadModal from './CSVDownloadModal';

import styles from './TopNFooter.module.css';
import { Select } from 'antd';
const { Option } = Select;

interface TopNFooterProps {
  disabled: boolean;
  onRemoveTable: () => void;
  onPrecisionChange: (precision: number) => void;
  currentPrecision: number;
  showPrecision: boolean;
  dimension: string;
  onTogglePoP: () => void;
  isPoPEnabled: boolean;
}

const TopNFooter = ({
  disabled,
  onRemoveTable,
  onPrecisionChange,
  onTogglePoP,
  currentPrecision,
  showPrecision,
  dimension,
  isPoPEnabled,
}: TopNFooterProps) => {
  const featureNameToEntityTypeMapping = useApplicationConfigStore((state) => state.featureNameToEntityTypeMapping);
  const updateShowBulkLabelDrawer = useLabelStore((state) => state.updateShowBulkLabelDrawer);

  const renderBulkLabelButton = () => {
    const entityType = featureNameToEntityTypeMapping.get(dimension);
    if (entityType == null) return null;

    return (
      <>
        <OspreyButton
          color={ButtonColors.LINK_GRAY}
          key="bulk"
          onClick={() => updateShowBulkLabelDrawer(true, dimension, entityType)}
        >
          <SelectOutlined />
          Bulk Label
        </OspreyButton>
      </>
    );
  };

  return (
    <div className={styles.menu}>
      <CSVDownloadModal disabled={disabled} dimension={dimension} />
      {renderBulkLabelButton()}
      <OspreyButton color={ButtonColors.LINK_GRAY} key="delta-pop" onClick={onTogglePoP} disabled={disabled}>
        PoP {isPoPEnabled ? 'On' : 'Off'}
      </OspreyButton>
      <OspreyButton color={ButtonColors.LINK_GRAY} key="remove" onClick={onRemoveTable}>
        <StopOutlined />
        Yeet Table
      </OspreyButton>
      {showPrecision && (
        <div>
          <b>Precision:</b>
          <Select
            bordered={false}
            onChange={onPrecisionChange}
            defaultValue={currentPrecision}
            style={{ width: 100, marginLeft: 0 }}
          >
            <Option value={0}>Default</Option>
            <Option value={0.1}>0.1</Option>
            <Option value={0.01}>0.01</Option>
            <Option value={0.001}>0.001</Option>
            <Option value={0.0001}>0.0001</Option>
          </Select>
        </div>
      )}
    </div>
  );
};

export default TopNFooter;

```

### `src/components/top_n/TopNTable.module.css`

```css
.tableWrapper {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--divider);
  border-radius: 4px;
  margin: 8px;
}

.tableWrapper:first-child {
  margin-top: 0;
}

.tableWrapper :global(.ant-table-cell) {
  padding: 6px !important;
}

.tableWrapper :global(.ant-table-column-sorters) {
  padding: 0 !important;
}

.countColumn {
  background-color: var(--background-secondary) !important;
  text-align: right !important;
  color: var(--text-light-primary);
  width: 30%;
}

.selectHeaderCell {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 4px !important;
}

.countHeaderCell {
  background-color: var(--background-tertiary) !important;
}

.countColumnTitle {
  font-weight: 600;
}

.countColumnTitleWithTooltip {
  gap: 8px;
}

```

### `src/components/top_n/TopNTable.tsx`

```typescript
import { InfoCircleOutlined } from '@ant-design/icons';
import { Table, Tooltip } from 'antd';
import { ColumnProps } from 'antd/lib/table';
import { SortOrder } from 'antd/lib/table/interface';

import { getTopNQueryResults } from '../../actions/EventActions';
import usePromiseResult from '../../hooks/usePromiseResult';
import { wrapEntityValuesWithLabelMenu } from '../../utils/EntityUtils';
import { renderFromPromiseResult } from '../../utils/PromiseResultUtils';
import useQueryStore from '../../stores/QueryStore';

import FeatureNameSelect from './FeatureNameSelect';
import styles from './TopNTable.module.css';
import TopNFooter from './TopNFooter';
import { DimensionDifference, DimensionResult, TopNResult } from '../../types/QueryTypes';

const SortOrders: { [key: string]: SortOrder } = {
  DESCEND: 'descend',
  ASCEND: 'ascend',
};

function getTableColumns(
  featureName: string,
  handleFeatureNameChange: (newDimension: string) => void,
  isPoPEnabled: boolean
): Array<ColumnProps<any>> {
  const columns = [
    {
      dataIndex: 'count',
      key: 'count',
      className: styles.countColumn,
      sortDirections: [SortOrders.DESCEND, SortOrders.ASCEND],
      sorter: (a: any, b: any) => a.count - b.count,
      defaultSortOrder: SortOrders.DESCEND,
      onHeaderCell: () => ({ className: styles.countHeaderCell }),
      title: () => <div className={styles.countColumnTitle}>Count</div>,
      render: (val: number | null) => (val == null ? '---' : val),
      width: isPoPEnabled ? '15%' : '30%',
    },
    {
      title: () => (
        <div className={styles.countColumnTitle} style={{ display: 'flex', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span>Δ PoP</span>
            <Tooltip title="PoP Disabled for Queries >45 days" mouseEnterDelay={0.5}>
              <InfoCircleOutlined style={{ fontSize: '12px' }} />
            </Tooltip>
          </div>
        </div>
      ),
      dataIndex: 'difference',
      key: 'difference',
      width: '20%',
      // Example render that formats the difference and colors it green/red:
      render: (val: number | null) => {
        if (val == null) return 'N/A';
        // Convert fraction to percent
        return <span style={{ color: val >= 0 ? 'green' : 'red' }}>{val}</span>;
      },
      sorter: (a: any, b: any) => a.difference - b.difference,
      defaultSortOrder: SortOrders.DESCEND,
      className: styles.countColumn,
      onHeaderCell: () => ({ className: styles.countHeaderCell }),
      hidden: !isPoPEnabled,
    },
    {
      title: () => <div className={styles.countColumnTitle}>%</div>,
      dataIndex: 'percent_diff',
      key: 'percent_diff',
      width: '10%',
      // Example render that formats the difference and colors it green/red:
      render: (val: number | null) => {
        if (val == null) return 'N/A';
        const style = { color: val >= 0 ? 'green' : 'red' };
        // Convert fraction to percent
        return <span style={style}>{val.toFixed(1) + '%'}</span>;
      },
      sorter: (a: any, b: any) => a.percent_diff - b.percent_diff,
      defaultSortOrder: SortOrders.DESCEND,
      className: styles.countColumn,
      onHeaderCell: () => ({ className: styles.countHeaderCell }),
      hidden: !isPoPEnabled,
    },
    {
      dataIndex: featureName,
      key: featureName,
      title: () => (
        <FeatureNameSelect selectedFeatureName={featureName} onFeatureNameChange={handleFeatureNameChange} />
      ),
      onHeaderCell: () => ({ className: styles.selectHeaderCell }),
      render: (val: string) => (featureName !== '' ? wrapEntityValuesWithLabelMenu(val, featureName) : val),
    },
  ];

  const displayedColumns = columns.filter((column) => !column.hidden);

  return displayedColumns;
}

interface TopNTableProps {
  onRemoveTable: (dimension: string) => void;
  onDimensionChange: (oldDimension: string, newDimension: string) => void;
  onPrecisionChange: (dimension: string, newPrecision: number) => void;
  onTogglePoP: (dimension: string) => void;
  dimension: string; // The column we wish to query https://druid.apache.org/docs/latest/querying/dimensionspecs.html
  showPrecision: boolean; // Whether to show or hide the precision selector on this TopN Table
  precision: number; // The precision to request from the TopN API. Accepts float values between 0 and 1 (i.e. 0.001)
  isPoPEnabled: boolean; // Whether to show or hide the PoP columns on this TopN Table
}

const TopNTable = ({
  onRemoveTable,
  onDimensionChange,
  onPrecisionChange,
  onTogglePoP,
  dimension,
  showPrecision,
  precision,
  isPoPEnabled,
}: TopNTableProps) => {
  const executedQuery = useQueryStore((state) => state.executedQuery);
  const entityFeatureFilters = useQueryStore((state) => state.entityFeatureFilters);

  const topNResult = usePromiseResult(async () => {
    const topN = await getTopNQueryResults({ ...executedQuery, entityFeatureFilters }, dimension, 100, precision);
    const currentPeriod = topN.current_period[0]?.result;
    const comparison = topN.comparison;

    // Disregard any records that don't have a current record on UI
    // Matches bulk label filter behavior
    if (!currentPeriod) {
      return { topN: [], queryDimension: dimension };
    }

    const dataWithDiff = currentPeriod.map((currentRow: DimensionResult) => {
      const key = currentRow[dimension];
      const comparisonRow = comparison?.[0]?.differences.find((row: DimensionDifference) => row.dimension_key === key);
      return {
        [dimension]: key,
        count: currentRow.count,
        difference: comparisonRow ? comparisonRow.difference : null,
        percent_diff: comparisonRow ? comparisonRow.percentage_change : null,
      };
    });
    return { topN: dataWithDiff, queryDimension: dimension };
  }, [executedQuery, entityFeatureFilters, dimension, precision]);

  const handleDimensionChange = (newDimension: string) => {
    onDimensionChange(dimension, newDimension);
  };

  const handlePrecisionChange = (newPrecision: number) => {
    onPrecisionChange(dimension, newPrecision);
  };

  const handleRemoveTable = () => {
    onRemoveTable(dimension);
  };

  const handleTogglePoP = () => {
    onTogglePoP(dimension);
  };

  const tableColumns = getTableColumns(dimension, handleDimensionChange, isPoPEnabled);

  return (
    <div className={styles.tableWrapper}>
      {renderFromPromiseResult(topNResult, ({ topN, queryDimension }) => (
        <>
          <Table
            showSorterTooltip={false}
            columns={tableColumns}
            dataSource={topN}
            rowKey={queryDimension}
            pagination={false}
            size="small"
            scroll={{ y: 400 }}
          />
          <TopNFooter
            onTogglePoP={handleTogglePoP}
            onRemoveTable={handleRemoveTable}
            onPrecisionChange={handlePrecisionChange}
            currentPrecision={precision}
            showPrecision={showPrecision}
            disabled={queryDimension === '' || topN.length === 0}
            dimension={queryDimension}
            isPoPEnabled={isPoPEnabled}
          />
        </>
      ))}
    </div>
  );
};

export default TopNTable;

```

### `src/hooks/usePromiseResult.tsx`

```typescript
import * as React from 'react';

export enum PromiseResultStatus {
  Resolving,
  Resolved,
  Rejected,
}

type Resolver<T> = () => Promise<T>;
export type PromiseResult<T> =
  | { status: PromiseResultStatus.Resolving }
  | { status: PromiseResultStatus.Resolved; value: T }
  | { status: PromiseResultStatus.Rejected; error: Error; retry: () => void };

export default function usePromiseResult<T>(resolver: Resolver<T>, deps: React.DependencyList = []): PromiseResult<T> {
  const [state, setState] = React.useState<PromiseResult<T>>({ status: PromiseResultStatus.Resolving });
  const [retryCounter, setRetryCounter] = React.useState<number>(0);

  React.useEffect(
    () => {
      // Set to false when the effect un-mounts, so we know to discard the result of the
      // promise.
      let isCurrent = true;
      // Regardless of what the state when we start running the effect, we need to transition back
      // to the resolving state.
      setState({ status: PromiseResultStatus.Resolving });

      const resolveData = async () => {
        try {
          const value = await resolver();
          if (isCurrent) {
            setState({ status: PromiseResultStatus.Resolved, value });
          }
        } catch (error: any) {
          // eslint-disable-next-line no-console
          console.error('Error while resolving promise', error);
          if (isCurrent) {
            const retry = () => {
              // Check if we're current, and only retry if we are. If someone calls `retry`, but we have
              // unmounted, or we've re-mounted the effect, we can ignore this request to retry.
              if (isCurrent) {
                // Increment the retry counter, which will cause the effect to re-mount, and trigger
                // a new loading indicator.
                setRetryCounter((x) => x + 1);
              }
            };
            setState({ status: PromiseResultStatus.Rejected, error, retry });
          }
        }
      };

      resolveData();

      return () => {
        isCurrent = false;
      };
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [retryCounter, ...deps]
  );

  return state;
}

```

### `src/hooks/useResizeObserver.tsx`

```typescript
import * as React from 'react';
import { ResizeObserver, ResizeObserverEntry } from '@juggle/resize-observer';

export default function useResizeObserver(
  element: HTMLElement | null,
  onUpdate?: (entry: ResizeObserverEntry) => void
): DOMRect | null {
  const [refRect, setRefRect] = React.useState<DOMRect | null>(null);

  React.useLayoutEffect(() => {
    if (element == null) return;

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      setRefRect(entry.target.getBoundingClientRect());
      onUpdate?.(entry);
    });

    resizeObserver.observe(element);

    return () => resizeObserver.disconnect();
  }, [onUpdate, element]);

  return refRect;
}

```

### `src/index.css`

```css
html {
  display: flex;
}

html,
body {
  background-color: var(--background-secondary) !important;
  min-height: 100%;
}

body {
  margin: 0;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans',
    'Helvetica Neue', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

code {
  font-family: source-code-pro, Menlo, Monaco, Consolas, 'Courier New', monospace;
}

#root,
.ant-app {
  height: 100%;
}

```

### `src/index.tsx`

```typescript
import './utils/ErrorReporting';
import './utils/DayjsSetup';
import ReactDOM from 'react-dom/client';

import 'antd/dist/reset.css';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root')!);
root.render(<App />);

```

### `src/lib/copyText.ts`

```typescript
// the clipboard api is not available when using a non-secure host (aside from localhost)
// this can be pretty common for some setups that are running i.e. on tailscale, so ideally
// we don't want to break things when a user tries to copy text somewhere. here we use a
// fallback when either that api is not available or `secureContext` is false
// see: https://developer.mozilla.org/en-US/docs/Web/API/Navigator/clipboard
export async function copyText(text: string): Promise<void> {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  } else {
    // create a textarea that gets appended to the body, then focus+copy text
    const body = document.body;
    const textarea = document.createElement('textarea');
    textarea.setAttribute('aria-hidden', 'true');
    body.appendChild(textarea);
    textarea.value = text;
    textarea.focus();
    textarea.select();

    // NOTE: execCommand is actually deprecated, so this might break in future browser versions
    // unfortunately. we'll log an error in the event that things do fail.
    // see: https://developer.mozilla.org/en-US/docs/Web/API/Document/execCommand
    try {
      document.execCommand('copy');
    } catch (err) {
      console.error(`copyText: fallback failed: ${err}`);
      // still throw the error so that calling code can optionally alert the user that the copy
      // failed
      throw err;
    } finally {
      textarea.remove();
    }
  }
}

```

### `src/models/DefaultFeature.tsx`

```typescript
import globToRegExp from 'glob-to-regexp';

export default class DefaultFeature {
  features: readonly string[];

  private actionNameSet: Set<string>;
  private actionNameRegularExpressions: RegExp[];

  constructor(actionNames: string[], features: string[]) {
    this.features = features;

    this.actionNameRegularExpressions = [];
    this.actionNameSet = new Set();

    for (const actionName of actionNames) {
      if (actionName.includes('*') || actionName.includes('?')) {
        this.actionNameRegularExpressions.push(globToRegExp(actionName));
      } else {
        this.actionNameSet.add(actionName);
      }
    }
  }

  appliesTo(actionName: string): boolean {
    return this.actionNameSet.has(actionName) || this.actionNameRegularExpressions.some((re) => re.test(actionName));
  }
}

```

### `src/react-app-env.d.ts`

```typescript
/// <reference types="react-scripts" />

```

### `src/stores/ApplicationConfigStore.tsx`

```typescript
import create from 'zustand';

import DefaultFeature from '../models/DefaultFeature';
import { LabelConnotation } from '../types/LabelTypes';

/// similar to ConfigType's `LabelInfo`, but with camel casing.
export interface LabelInfo {
  validFor: Set<string>;
  connotation: LabelConnotation;
  description: string;
}

export type LabelInfoMapping = Map<string, LabelInfo>;
export type FeatureNameToEntityTypeMapping = Map<string, string>;
export type FeatureNameToValueTypeMapping = Map<string, string>;
export type EntityToFeatureSetMapping = Map<string, Set<string>>;
export type ExternalLinkMapping = Map<string, string>;
export type KnownFeatureCategoriesMapping = Map<string, string[]>;
export type OptionInfoMapping = Map<string, string>;

export interface FeatureLocation {
  name: string;
  source_path: string;
  source_line: number;
  source_snippet: string;
}

export interface KnownFeatureCategories {
  [category: string]: string[];
}

export interface ApplicationConfig {
  defaultSummaryFeatures: DefaultFeature[];
  featureNameToEntityTypeMapping: FeatureNameToEntityTypeMapping;
  featureNameToValueTypeMapping: FeatureNameToValueTypeMapping;
  entityToFeatureSetMapping: EntityToFeatureSetMapping;
  externalLinks: ExternalLinkMapping;
  labelInfoMapping: LabelInfoMapping;
  ruleInfoMapping: OptionInfoMapping;
  knownFeatureNames: Set<string>;
  knownFeatureCategories: KnownFeatureCategories;
  knownActionNames: Set<string>;
  currentUser: { email?: string };
}

type ApplicationConfigStore = {
  updateApplicationConfig: (config: ApplicationConfig) => void;
  isRecordingClicks: boolean;
} & ApplicationConfig;

const useApplicationConfigStore = create<ApplicationConfigStore>((set) => ({
  defaultSummaryFeatures: [],
  featureNameToEntityTypeMapping: new Map(),
  featureNameToValueTypeMapping: new Map(),
  entityToFeatureSetMapping: new Map(),
  externalLinks: new Map(),
  labelInfoMapping: new Map(),
  knownFeatureNames: new Set(),
  knownFeatureCategories: {},
  knownActionNames: new Set(),
  ruleInfoMapping: new Map(),
  updateApplicationConfig: (config: ApplicationConfig) => set(() => ({ ...config })),
  isRecordingClicks: false,
  currentUser: {},
}));

export default useApplicationConfigStore;

```

### `src/stores/BulkActionStore.tsx`

```typescript
import create from 'zustand';
import { BulkActionJob, StartBulkActionRequest, StartBulkActionResponse } from '../types/BulkActionTypes';
import { startBulkAction, uploadCompleted, uploadFile, getJobs, cancelJob } from '../actions/BulkJobActions';

export interface ClientFileUploadRequest {
  file: File;
}

function isJobInProgress(job: BulkActionJob): boolean {
  return job.status === 'processing' || job.status === 'uploaded' || job.status === 'parsing';
}

export type StartBulkActionJobRequest = StartBulkActionRequest & ClientFileUploadRequest;

interface BulkActionStore {
  startBulkAction: (request: StartBulkActionJobRequest) => Promise<StartBulkActionResponse>;
  getJobs: () => Promise<(() => void) | void>;
  jobs: BulkActionJob[];
  cancelJob: (jobId: string) => Promise<void>;
  jobPollingInProgress: boolean;
}

const useBulkActionStore = create<BulkActionStore>((set, get) => ({
  startBulkAction: async (request: StartBulkActionJobRequest): Promise<StartBulkActionResponse> => {
    const { file, ...startRequest } = request;

    const result = await startBulkAction(startRequest);

    if (result.url == null) {
      throw new Error('Failed to start bulk action, missing upload url: ' + result.id);
    }

    await uploadFile(result.url, request.file);
    await uploadCompleted(result.id);

    return result;
  },
  getJobs: async (): Promise<(() => void) | void> => {
    const result = await getJobs();
    // Sort jobs by created_at in descending order (most recent first)
    const sortedJobs = [...result].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    set({ jobs: sortedJobs });

    // Check if there are any in-progress jobs
    const hasInProgressJobs = sortedJobs.some(isJobInProgress);

    if (hasInProgressJobs) {
      set({ jobPollingInProgress: true });
      const pollInterval = setInterval(async () => {
        const updatedJobs = await getJobs();
        // Sort updated jobs as well
        const sortedUpdatedJobs = [...updatedJobs].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        set({ jobs: sortedUpdatedJobs });

        // Stop polling if no more in-progress jobs
        const stillInProgress = sortedUpdatedJobs.some(isJobInProgress);

        if (!stillInProgress) {
          clearInterval(pollInterval);
          set({ jobPollingInProgress: false });
        }
      }, 5000); // Poll every 5 seconds

      // Return cleanup function
      return () => clearInterval(pollInterval);
    } else {
      set({ jobPollingInProgress: false });
    }
  },
  jobs: [],
  jobPollingInProgress: false,
  cancelJob: async (jobId: string): Promise<void> => {
    await cancelJob(jobId);
    // update the job status in the store
    const jobs = get().jobs;
    const job = jobs.find((job) => job.id === jobId);
    if (job) {
      job.status = 'cancelled';
    }
    set({ jobs: jobs });
  },
}));

export default useBulkActionStore;

```

### `src/stores/EntityStore.tsx`

```typescript
import create from 'zustand';

import { Entity } from '../types/EntityTypes';
import { EventCountsByFeatureForEntityQuery } from '../types/QueryTypes';

export const DEFAULT_LABELS = { positive: [], negative: [], neutral: [] };

export interface EntityViewParams {
  entityType: string;
  entityId: string;
}

interface EntityStore {
  selectedEntity: Entity | null;
  updateSelectedEntity: (entity: Entity | null) => void;
  showLabelDrawer: boolean;
  updateShowLabelDrawer: (isVisible: boolean) => void;
  eventCountByFeature: EventCountsByFeatureForEntityQuery;
  totalEventCount: number;
}

const useEntityStore = create<EntityStore>((set) => ({
  selectedEntity: null,
  updateSelectedEntity: (newSelectedEntity: Entity | null) => set(() => ({ selectedEntity: newSelectedEntity })),
  showLabelDrawer: false,
  updateShowLabelDrawer: (isVisible: boolean) => set(() => ({ showLabelDrawer: isVisible })),
  eventCountByFeature: {},
  totalEventCount: 0,
}));

export default useEntityStore;

```

### `src/stores/ErrorStore.tsx`

```typescript
import create from 'zustand';

interface ErrorStore {
  errors: Set<string>;
  clearErrors(): void;
}

const useErrorStore = create<ErrorStore>((set) => ({
  errors: new Set(),
  clearErrors: () => set(() => ({ errors: new Set() })),
}));

export default useErrorStore;

```

### `src/stores/LabelStore.tsx`

```typescript
import create from 'zustand';

interface LabelStore {
  bulkLabelEntityType: string | null;
  bulkLabelFeatureName: string | null;
  showBulkLabelDrawer: boolean;
  updateShowBulkLabelDrawer: (isVisible: boolean, featureName: string | null, entityType: string | null) => void;
}

const useLabelStore = create<LabelStore>((set) => ({
  bulkLabelEntityType: null,
  bulkLabelFeatureName: null,
  showBulkLabelDrawer: false,
  updateShowBulkLabelDrawer: (isVisible: boolean, featureName: string | null, entityType: string | null) =>
    set(() => ({ showBulkLabelDrawer: isVisible, bulkLabelFeatureName: featureName, bulkLabelEntityType: entityType })),
}));

export default useLabelStore;

```

### `src/stores/QueryStore.tsx`

```typescript
import { createBrowserHistory } from 'history';
import create from 'zustand';

import { Feature } from '../types/EntityTypes';
import { BaseQuery, ScanQueryOrder, CustomSummaryFeatures, TopNTable, Chart } from '../types/QueryTypes';
import {
  extractQueryStateFromSearchParams,
  getSearchParamsForExecutedQuery,
  setSearchParamsForEntityView,
} from '../utils/QueryStoreUtils';
import { baseQueryEquals } from '../utils/QueryUtils';

export const history = createBrowserHistory();

// If the application is loaded on the entity route with an empty query string,
// set the query string to the default entity query before extracting
// query state.
setSearchParamsForEntityView(history);

export interface QueryStore {
  executedQuery: BaseQuery;
  sortOrder: ScanQueryOrder;
  topNTables: Map<string, TopNTable>;
  charts: Array<Chart>;
  entityFeatureFilters: Set<string>;

  updateExecutedQuery: (query: BaseQuery) => void;
  updateSortOrder: (sortOrder: ScanQueryOrder) => void;
  updateTopNTables: (topNTables: Map<string, TopNTable>) => void;
  addChart: (chart: Chart) => void;
  updateChart: (index: number, chart: Chart) => void;
  updateEntityFeatureFilters: (entityFeatureFilters: Set<string>) => void;

  /*
   * If you are performing an asynchronous operation, such as fetching data from an API, the current query
   * may have changed. This utility function will check if the query provided matches the current query,
   * and if it does, will invoke the provided `fn`.
   */
  applyIfQueryIsCurrent(query: BaseQuery, fn: () => unknown): void;

  queuedQueryFilters: Feature[];
  updateQueuedQueryFilters: (shortcutUpdates: Feature[]) => void;

  customSummaryFeatures: CustomSummaryFeatures;
  updateCustomSummaryFeatures: (features: CustomSummaryFeatures) => void;
}

const _updateQueryStringCharts = (charts: Array<Chart>) => {
  const queryString = new URLSearchParams(history.location.search);
  queryString.delete('chart');
  charts.filter((g) => !g.deleted).forEach((chart) => queryString.append('chart', chart.query));
  history.push({ search: `?${queryString.toString()}` });
};

const useQueryStore = create<QueryStore>((set, get) => ({
  ...extractQueryStateFromSearchParams(history.location),

  updateExecutedQuery: (query: BaseQuery) => {
    const queryString = getSearchParamsForExecutedQuery(query, history.location);
    history.push({ search: `?${queryString.toString()}` });
  },
  updateSortOrder: (sortOrder: ScanQueryOrder) => {
    const queryString = new URLSearchParams(history.location.search);
    queryString.set('order', sortOrder);

    history.push({ search: `?${queryString.toString()}` });
  },
  updateTopNTables: (topNTables: Map<string, TopNTable>) => {
    const queryString = new URLSearchParams(history.location.search);

    queryString.delete('topn');
    topNTables.forEach((table, __) => queryString.append('topn', table.asQueryParam()));

    history.push({ search: `?${queryString.toString()}` });
  },
  addChart: (chart: Chart) =>
    set(({ charts }) => {
      const newCharts = [...charts, chart];
      _updateQueryStringCharts(newCharts);
      return { charts: newCharts };
    }),
  updateChart: (index: number, chart: Chart) =>
    set(({ charts }) => {
      const newCharts = [...charts];
      newCharts[index] = chart;
      _updateQueryStringCharts(newCharts);
      return { charts: newCharts };
    }),
  updateEntityFeatureFilters: (entityFeatureFilters: Set<string>) => {
    const queryString = new URLSearchParams(history.location.search);

    queryString.delete('entityFeatureFilters');
    entityFeatureFilters.forEach((filter) => queryString.append('entityFeatureFilters', filter));

    history.push({ search: `?${queryString.toString()}` });
  },

  applyIfQueryIsCurrent: (query: BaseQuery, fn: () => unknown) => {
    const { executedQuery } = get();
    if (baseQueryEquals(executedQuery, query)) {
      fn();
    }
  },

  queuedQueryFilters: [],
  updateQueuedQueryFilters: (shortcutUpdates: Feature[]) => set(() => ({ queuedQueryFilters: shortcutUpdates })),

  updateCustomSummaryFeatures: (features: CustomSummaryFeatures) => {
    const queryString = new URLSearchParams(history.location.search);

    queryString.delete('customSummaryFeatures');
    if (features != null) {
      features.forEach((feature) => queryString.append('customSummaryFeatures', feature));
    }

    history.push({ search: `?${queryString.toString()}` });
  },
}));

export default useQueryStore;

```

### `src/stores/RulesVisualizerStore.tsx`

```typescript
import create from 'zustand';
import { Node, Edge } from '../types/RulesVisualizerTypes';

interface RuleVizGraph {
  nodes: Node[] | null;
  edges: Edge[] | null;
  selectedFeature?: string;
  selectedFeatureType?: 'Action' | 'Label';
  errorMessage?: string;
}

type RulesVisualizerStore = {
  updateRuleVizGraph: (ruleVizGraph: RuleVizGraph) => void;
} & RuleVizGraph;

const useRulesVisualizerStore = create<RulesVisualizerStore>((set) => ({
  nodes: null,
  edges: null,
  updateRuleVizGraph: (ruleVizGraph: RuleVizGraph) => set(() => ({ ...ruleVizGraph })),
}));

export default useRulesVisualizerStore;

```

### `src/stores/SavedQueryStore.tsx`

```typescript
import create from 'zustand';

import { SavedQuery } from '../types/QueryTypes';

interface SavedQueryStore {
  savedQueries: SavedQuery[];
  updateSavedQueries: (savedQueries: SavedQuery[]) => void;
}

const useSavedQueryStore = create<SavedQueryStore>((set) => ({
  savedQueries: [],
  updateSavedQueries: (savedQueries: SavedQuery[]) => set(() => ({ savedQueries })),
}));

export default useSavedQueryStore;

```

### `src/stores/SearchParamsStateListener.tsx`

```typescript
import { Location } from 'history';
import { isEqual } from 'lodash';

import { extractQueryStateFromSearchParams, setSearchParamsForEntityView } from '../utils/QueryStoreUtils';
import { baseQueryEquals, topNEquals } from '../utils/QueryUtils';
import useQueryStore, { history, QueryStore } from './QueryStore';

import { Routes } from '../Constants';

history.listen((location: Location) => {
  if (location.search === '') {
    if (location.pathname === Routes.HOME) {
      useQueryStore.setState(extractQueryStateFromSearchParams(location));
    } else {
      setSearchParamsForEntityView(history);
    }
    return;
  }

  const { executedQuery, sortOrder, topNTables, customSummaryFeatures, entityFeatureFilters } =
    useQueryStore.getState();
  const newState = extractQueryStateFromSearchParams(location);

  if (!isEqual(newState.customSummaryFeatures, customSummaryFeatures)) {
    useQueryStore.setState({ customSummaryFeatures: newState.customSummaryFeatures });
    return;
  }

  if (!isEqual(newState.entityFeatureFilters, entityFeatureFilters)) {
    useQueryStore.setState({ entityFeatureFilters: newState.entityFeatureFilters });
    return;
  }

  const stateUpdate: QueryStore = {} as any;

  if (!baseQueryEquals(executedQuery, newState.executedQuery)) {
    stateUpdate.executedQuery = newState.executedQuery;
  }

  if (newState.sortOrder !== sortOrder) {
    stateUpdate.sortOrder = newState.sortOrder;
  }

  if (!topNEquals(newState.topNTables, topNTables)) {
    stateUpdate.topNTables = newState.topNTables;
  }

  useQueryStore.setState(stateUpdate);
});

```

### `src/styles/Colors.module.css`

```css
:root {
  /* Backgrounds */
  --background-primary: #ffffff;
  --background-secondary: #f7f8f9;
  --background-secondary-alt: #f2f3f5;
  --background-tertiary: #dbdcdf;

  /* Text for Light Backgrounds */
  --text-light-headings-primary: #252527;
  --text-light-headings-secondary: #5f626d;
  --text-light-primary: #3c3c40;
  --text-light-secondary: #656e7b;
  --text-light-disabled: #a8aeb8;

  /* Text for Dark Backgrounds */
  --text-dark-headings: #ffffff;
  --text-dark-primary: #ebebeb;
  --text-dark-secondary: #cdd0d6;
  --text-dark-disabled: #858e9b;

  /* Brand */
  --brand-primary: #1227ce;
  --brand-dark: #0c1b8d;

  /* Links */
  --link-primary: #0075e0;
  --link-dark: #1153a6;
  --link-muted: #cae0f9;
  --link-white: #ffffff;
  --link-grey: #252527;
  --link-light-hover: #e4effc;

  /* Status */
  --success-primary: #3e7025;
  --success-muted: #e6f2df;
  --error-primary: #b23a32;
  --error-muted: #f5dedc;
  --warning-primary: #faad14;
  --warning-muted: #feefd2;

  /* Icons */
  --icon-primary: #535a65;
  --icon-active: #25282d;
  --icon-hover: #3c4149;
  --icon-muted: #9aa1ac;

  /* Dividers */
  --divider: #dbdcdf;
}

```

### `src/types/BulkActionTypes.tsx`

```typescript
export interface StartBulkActionRequest {
  job_name: string;
  job_description: string;
  workflow_name: string;
  file_name: string;
  entity_type: string;
}

export interface StartBulkActionResponse {
  id: string;
  url: string; // upload url for the file
}

export interface BulkActionJob {
  id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
  description: string;
  entity_type: string;
  action_workflow_name: string;
  total_rows: number;
  processed_rows: number;
  error: string;
  user_id: string;
}

```

### `src/types/BulkJobTypes.tsx`

```typescript
export interface BulkJobTask {
  created_at: number;
  task_id: string;
  initiated_by: string;
  task_status: string;
  attempts: number;
  updated_at: number;

  label_status: string;
  label_name: string;
  dimension: string;
  entities_collected: number | undefined;
  entities_labeled: number | undefined;
  total_entities_to_label: number | undefined;
  expected_total_entities_to_label: number | undefined;

  query_filter: string | undefined;
  query_start: number;
  query_end: number;
  label_reason: string;

  no_limit: boolean;
}

// A special class for formatting the way the Bulk Job Task will be dispalyed on the bulk jobs page
export class FormattedBulkJobTask {
  task: BulkJobTask;
  formatted_task: Map<string, string>;

  constructor(task: BulkJobTask) {
    this.task = task;
    this.formatted_task = new Map();

    const addItem = (key: string, value: any) => {
      if (value === null) {
        this.formatted_task.set(key, 'None');
        return;
      }
      this.formatted_task.set(key, String(value));
    };

    let remainingEntities: string = 'N/A';
    if (!this.isCollecting() && task.total_entities_to_label != null && task.entities_labeled != null) {
      remainingEntities = (task.total_entities_to_label - task.entities_labeled).toLocaleString('en-US');
    } else if (
      this.isCollecting() &&
      task.expected_total_entities_to_label != null &&
      task.entities_collected != null
    ) {
      remainingEntities = (task.expected_total_entities_to_label - task.entities_collected).toLocaleString('en-US');
    }

    addItem('Task ID', task.task_id);
    addItem('Initiator', task.initiated_by);
    addItem(
      'Status',
      task.task_status +
        (this.isTaskFinal()
          ? ' as of ' + new Date(task.updated_at * 1000)
          : this.getEstimatedTimeRemaining() !== ''
            ? ' (estimated ' +
              this.getEstimatedTimeRemaining() +
              ' ' +
              (this.isCollecting() ? 'until labelling' : 'remaining') +
              ')'
            : ' (estimate pending)') +
        ' (' +
        task.attempts +
        ' total attempt' +
        (task.attempts === 1 ? '' : 's') +
        ')'
    );

    addItem('Label status applied', task.label_status);
    addItem('Label used', task.label_name + ' on ' + task.dimension);

    if (this.isCollecting()) {
      addItem(
        'Entities collected',
        (task.entities_collected === undefined ? 'N/A' : task.entities_collected.toLocaleString('en-US')) +
          (remainingEntities !== '0' && remainingEntities !== 'N/A'
            ? ' (~' + remainingEntities + (!this.isTaskFinal() ? ' remaining)' : ' dropped)')
            : '')
      );
    } else {
      addItem(
        'Entities labelled',
        task.entities_labeled === undefined
          ? 'N/A'
          : task.entities_labeled.toLocaleString('en-US') +
              (remainingEntities !== '0'
                ? ' (' + remainingEntities + (!this.isTaskFinal() ? ' remaining)' : ' dropped)')
                : '')
      );
    }

    addItem('Query filter', task.query_filter);
    addItem('Query range', new Date(task.query_start * 1000) + ' - ' + new Date(task.query_end * 1000));
    addItem('Label reason', task.label_reason);
  }

  isTaskFinal(): boolean {
    return ['FAILED', 'COMPLETE'].includes(this.task.task_status.toUpperCase());
  }

  isCollecting(): boolean {
    return this.task.task_status.toUpperCase() === 'COLLECTING';
  }

  isLabelling(): boolean {
    return this.task.task_status.toUpperCase() === 'LABELLING';
  }

  /**
   * @returns A formatted string with hours, minutes, and seconds remaining on this task (if applicable)
   */
  getEstimatedTimeRemaining(): string {
    let current_count: number;
    let total_count: number;
    const get_or_default = (value: number | undefined, default_value: number): number => {
      if (!value) {
        return default_value;
      } else {
        return value;
      }
    };
    if (this.isCollecting()) {
      current_count = get_or_default(this.task.entities_collected, 0);
      total_count = get_or_default(this.task.expected_total_entities_to_label, 0);
    } else if (this.isLabelling()) {
      current_count = get_or_default(this.task.entities_labeled, 0);
      total_count = get_or_default(this.task.total_entities_to_label, 0);
    } else {
      return '';
    }
    const timeElapsed: number = Date.now() - new Date(this.task.created_at * 1000).valueOf();
    const estimatedFinishDate: Date =
      this.isTaskFinal() || current_count === undefined || total_count === undefined
        ? new Date(this.task.updated_at * 1000)
        : new Date((total_count / current_count - 1) * timeElapsed + Date.now());
    let tempTime = (estimatedFinishDate.valueOf() - Date.now()) / 1000;
    const secRemaining = Math.floor(tempTime % 60);
    tempTime /= 60;
    const minRemaining = Math.floor(tempTime % 60);
    tempTime /= 60;
    const hrsRemaining = Math.floor(tempTime);
    const estimatedTimeRemaining: string = this.isTaskFinal()
      ? ''
      : (
          (hrsRemaining > 0 ? hrsRemaining + 'h ' : '') +
          (minRemaining > 0 ? minRemaining + 'm ' : '') +
          (secRemaining > 0 ? secRemaining + 's ' : minRemaining <= 0 && hrsRemaining <= 0 ? '0s ' : '')
        ).trimEnd();
    return estimatedTimeRemaining;
  }

  getMap(): Map<string, string> {
    return this.formatted_task;
  }

  // Returns a query url that has the same start, end, and filters as the original query
  getQueryUrl(): string {
    return (
      window.location.origin +
      '/?start=' +
      encodeURIComponent(new Date(this.task.query_start * 1000).toISOString()) +
      '&end=' +
      encodeURIComponent(new Date(this.task.query_end * 1000).toISOString()) +
      '&queryFilter=' +
      encodeURIComponent(this.task.query_filter ? this.task.query_filter : '') +
      '&topn=' +
      encodeURIComponent(this.task.dimension)
    );
  }
}

```

### `src/types/ConfigTypes.tsx`

```typescript
import { LabelConnotation } from './LabelTypes';

interface RawDefaultSummaryFeature {
  actions: string[];
  features: string[];
}

interface RawExternalLinkMapping {
  [entityType: string]: string;
}
interface RawLabelInfo {
  valid_for: string[];
  connotation: LabelConnotation;
  description: string;
}
interface RawLabelInfoMapping {
  [labelName: string]: RawLabelInfo;
}
interface RawFeatureNameToEntityTypeMapping {
  [featureName: string]: string;
}
interface RawFeatureNameToValueTypeMapping {
  [featureName: string]: string;
}
interface RawRuleInfoMapping {
  [ruleName: string]: string;
}

export interface FeatureLocation {
  name: string;
  source_path: string;
  source_line: number;
  source_snippet: string;
}

export interface RawUIConfig {
  default_summary_features: RawDefaultSummaryFeature[];
  feature_name_to_entity_type_mapping: RawFeatureNameToEntityTypeMapping;
  feature_name_to_value_type_mapping: RawFeatureNameToValueTypeMapping;
  external_links: RawExternalLinkMapping;
  known_feature_locations: FeatureLocation[];
  known_action_names: string[];
  label_info_mapping: RawLabelInfoMapping;
  rule_info_mapping: RawRuleInfoMapping;
  current_user: { email: string };
}

```

### `src/types/DocTypes.tsx`

```typescript
export interface UdfCategory {
  name: string | null;
  udfs: UdfMethodSpec[];
}

export interface UdfMethodSpec {
  name: string;
  doc: string | null;
  argument_specs: UdfArgumentSpec[];
  return_type: string;
  category: string | null;
}

export interface UdfArgumentSpec {
  name: string;
  type: string;
  default: string | null;
  doc: string | null;
}

```

### `src/types/EntityTypes.tsx`

```typescript
import { SortedLabels } from './LabelTypes';

export interface Entity {
  type: string;
  id: string;
  labels: SortedLabels;
  hasLabels: boolean;
}

export interface Feature {
  value: string | null;
  featureName: string;
}

```

### `src/types/LabelTypes.tsx`

```typescript
export enum LabelStatus {
  REMOVED,
  ADDED,
  MANUALLY_REMOVED,
  MANUALLY_ADDED,
}

export const LabelStatusAPIMapping: Record<LabelStatus, string> = {
  [LabelStatus.ADDED]: 'ADDED',
  [LabelStatus.REMOVED]: 'REMOVED',
  [LabelStatus.MANUALLY_ADDED]: 'MANUALLY_ADDED',
  [LabelStatus.MANUALLY_REMOVED]: 'MANUALLY_REMOVED',
};

export interface KeyedLabels {
  [labelName: string]: Label;
}

export interface KeyedReasons {
  [reasonName: string]: LabelReason;
}

export type SortedLabels = Record<LabelConnotation, Label[]>;

export interface LabelState {
  status: LabelStatus;
  reasons: KeyedReasons;
}

export interface Label {
  name: string;
  status: LabelStatus;
  // key here is the rule name.
  reasons: KeyedReasons;
  previous_states: LabelState[];
}

export interface LabelMutation {
  label_name: string;
  status: LabelStatus;
  reason: string;
  expires_at?: string;
}

export interface LabelMutationDetails {
  added: string[];
  updated: string[];
  removed: string[];
  unchanged: string[];
}

export interface LabelMutationResult {
  labels: Label[];
  mutation_result: LabelMutationDetails;
}

export interface EntityLabels {
  expires_at: Date | null;
  labels: KeyedLabels;
}

export interface LabelReason {
  pending: boolean;
  // For example, this could be `Signed up with suspicious domain {EmailDomain}`.
  description: string;
  // And this would be {"EmailDomain": "shadywebsite.com"}
  features: { [entityName: string]: string };
  created_at: string;
  expires_at: string | null;
}

export enum LabelConnotation {
  POSITIVE = 'positive',
  NEGATIVE = 'negative',
  NEUTRAL = 'neutral',
}

export const LabelConnotations: readonly LabelConnotation[] = [
  LabelConnotation.NEGATIVE,
  LabelConnotation.POSITIVE,
  LabelConnotation.NEUTRAL,
];

```

### `src/types/QueryTypes.tsx`

```typescript
import type { ManipulateType } from 'dayjs';
import { FeatureLocation } from './ConfigTypes';

interface IntervalOption {
  label: string;
  durationConstructor: [number, ManipulateType];
}

function intervalOption(duration: number, timeUnit: ManipulateType): IntervalOption {
  const timeUnitTitleCased = `${timeUnit[0].toUpperCase()}${timeUnit.substring(1)}`;
  const label = duration > 1 ? `Last ${duration} ${timeUnitTitleCased}s` : `Last ${timeUnitTitleCased}`;

  return {
    label,
    durationConstructor: [duration, timeUnit],
  };
}

export const IntervalOptions = {
  oneSecond: intervalOption(1, 'second'),
  tenMinutes: intervalOption(10, 'minute'),
  thirtyMinutes: intervalOption(30, 'minute'),
  hour: intervalOption(1, 'hour'),
  twoHours: intervalOption(2, 'hour'),
  fourHours: intervalOption(4, 'hour'),
  eightHours: intervalOption(8, 'hour'),
  twelveHours: intervalOption(12, 'hour'),
  day: intervalOption(1, 'day'),
  twoDays: intervalOption(2, 'day'),
  week: intervalOption(1, 'week'),
  twoWeeks: intervalOption(2, 'week'),
  month: intervalOption(1, 'month'),
  twoMonths: intervalOption(2, 'month'),
  threeMonths: intervalOption(3, 'month'),
};

export type MomentRangeValues = keyof typeof IntervalOptions;
export type DefaultIntervals = MomentRangeValues | 'custom' | null;

export interface BaseQuery {
  interval: DefaultIntervals;
  start: string;
  end: string;
  queryFilter: string;
}

export type BaseQueryRequest = BaseQuery & {
  entityFeatureFilters?: Set<string>;
};

export class Chart {
  query: string;
  deleted: boolean;

  constructor(query: string, deleted: boolean) {
    this.query = query;
    this.deleted = deleted;
  }

  static fromQueryParam(data: string): Chart {
    return new Chart(data, false);
  }
}

export class TopNTable {
  dimension: string;
  showPrecision: boolean;
  precision: number;
  isPoPEnabled: boolean;

  constructor(dimension: string, precision: number = 0, showPrecision: boolean = true, isPoPEnabled: boolean = false) {
    this.dimension = dimension;
    this.showPrecision = showPrecision;
    this.precision = precision;
    this.isPoPEnabled = isPoPEnabled;
  }

  asQueryParam() {
    let res = this.dimension;
    if (this.isPoPEnabled) {
      res += '.PoP';
    }
    if (this.precision === 0) {
      return res;
    }
    return res + ',' + String(this.precision);
  }

  static fromQueryParam(data: string | TopNTable): TopNTable {
    if (typeof data !== 'string') {
      return data;
    }

    let isPoPEnabled = false;
    if (data.includes('.PoP')) {
      isPoPEnabled = true;
      data = data.replaceAll('.PoP', '');
    }

    if (data.indexOf(',') != -1) {
      const splitData = data.split(',');

      let precision = Number.parseFloat(splitData[1]);
      if (isNaN(precision)) {
        precision = 0;
      }

      return new TopNTable(splitData[0], precision, true, isPoPEnabled);
    } else {
      return new TopNTable(data, undefined, undefined, isPoPEnabled);
    }
  }
}

export enum ScanQueryOrder {
  ASCENDING = 'ASCENDING',
  DESCENDING = 'DESCENDING',
}

export interface QueryState {
  executedQuery: BaseQuery;
  topNTables: Map<string, TopNTable>;
  sortOrder: ScanQueryOrder;
  charts: Array<Chart>;
}

interface EntityRequestData {
  id: string;
  type: string;
  feature_filters: string[] | null;
}

export interface QueryRequest {
  start: string;
  end: string;
  query_filter: string;
  entity: EntityRequestData | null;
}

export interface QueryRecordRequest {
  query_filter: string;
  date_range: [string, string];
  top_n: string[];
  sort_order: ScanQueryOrder;
}

export interface OspreyEvent {
  timestamp: string;
  id: string;
  extracted_features: { [key: string]: any };
}

export interface ScanResult {
  events: OspreyEvent[];
  offset: string | null;
  queryStart: string | null;
}

export type ScanQueryRequest = QueryRequest & {
  limit: number;
  next_page?: string;
  order: ScanQueryOrder;
};

export interface DimensionResult {
  count: number;
  [key: string]: string | number;
}

export interface TopNResult {
  timestamp: string;
  result: DimensionResult[];
}

export interface DimensionDifference {
  [key: string]: string | number;
  current_count: number;
  previous_count: number;
  difference: number;
  percentage_change: number;
}

export interface TopNComparison {
  differences: DimensionDifference[];
}

export interface TopNComparisonResult {
  comparison: TopNComparison[];
  current_period: TopNResult[];
  previous_period: TopNResult[];
}

export interface TimeseriesResult {
  timestamp: string;
  result: {
    count: number;
    [key: string]: number;
  };
}

export interface EventCountsByFeatureForEntityQuery {
  [featureName: string]: number;
}

export interface StoredExecutionResult {
  id: string;
  extracted_features: { [key: string]: any };
  timestamp: string;
  action_data: { [key: string]: any };
  error_traces: Array<{
    rules_source_location: string;
    traceback: string;
  }>;
}

export interface QueryRecord {
  id: string;
  parent_id?: string;
  executed_at: number;
  executed_by: string;
  query_filter: string;
  date_range: { start: string; end: string };
  top_n: TopNTable[];
  sort_order: ScanQueryOrder;
}

export interface SavedQuery {
  id: string;
  name: string;
  query_id: string;
  saved_by: string;
  saved_at: number;
  query: QueryRecord;
}

export type CustomSummaryFeatures = string[] | null;
export type EntityFeatureFilters = Set<string>;

export interface FeatureLocations {
  locations: Array<FeatureLocation> | undefined;
}

```

### `src/types/RulesVisualizerTypes.tsx`

```typescript
import { DagreLayoutOptions } from 'cytoscape-dagre';
import { Core, CssStyleDeclaration, ElementsDefinition, NodeSingular } from 'cytoscape';
import { ReactElement } from 'react';

export interface HierarchicalGraphOptions {
  elements: ElementsDefinition;
  nodeStyle?: Partial<CssStyleDeclaration>;
  edgeStyle?: Partial<CssStyleDeclaration>;
  layoutOptions?: Partial<DagreLayoutOptions>;
  onLoad?: (cy: Core) => void;
  ToolTip?: ({ node }: { node: NodeSingular }) => ReactElement;
}

export interface Node {
  id: number;
  name: string;
  num_children: number;
  type: string;
  label_type?: string;
  label_name?: string;
  entity_name?: string;
  file_path: string;
  value: string | string[];
}

export interface Edge {
  source: number;
  target: number;
  weight: number;
  color: string;
}

export enum NodeType {
  Label = 'Label',
  Rule = 'Rule',
}

export enum LabelType {
  Check = 'HasLabel',
  Add = 'LabelAdd',
  Remove = 'LabelRemove',
}

```

### `src/uikit/Collapse.module.css`

```css
.header {
  position: relative;
}

.arrowIconWrapper {
  position: absolute;
  height: 100%;
  cursor: pointer;
  display: flex;
  align-items: center;
}

.arrowIconWrapperLeft {
  composes: arrowIconWrapper;
  left: 6px;
}

.arrowIconWrapperRight {
  composes: arrowIconWrapper;
  right: 6px;
}

.arrowIcon {
  transition: all 0.2s ease-in-out;
}

.arrowIconActive {
  transform: rotate(90deg);
}

.contentWrapper {
  overflow: hidden;
  transition: all 0.2s ease-in-out;
}

```

### `src/uikit/Collapse.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';

import useResizeObserver from '../hooks/useResizeObserver';
import ArrowIcon from './icons/ArrowIcon';

import { Colors } from '../Constants';
import styles from './Collapse.module.css';

interface CollapseProps {
  header: React.ReactNode;
  children: React.ReactNode;
  isActive: boolean;
  onClick: () => void;
  headerClassName?: string;
  contentClassName?: string;
  arrowWrapperClassName?: string;
  defaultArrowPosition?: boolean;
}

const Collapse = ({
  header,
  children,
  isActive,
  onClick,
  headerClassName,
  contentClassName,
  arrowWrapperClassName,
  defaultArrowPosition = true,
}: CollapseProps) => {
  const contentRef = React.useRef(null);
  const contentRect = useResizeObserver(contentRef.current);

  const maxHeight = contentRect?.height ?? 0;

  return (
    <div className={styles.__invalid_collapse}>
      {/* eslint-disable-next-line */}
      <div className={classNames(styles.header, headerClassName)} onClick={onClick}>
        <div
          className={classNames(
            defaultArrowPosition ? styles.arrowIconWrapperLeft : styles.arrowIconWrapperRight,
            arrowWrapperClassName
          )}
        >
          <ArrowIcon
            color={Colors.ICON_MUTED}
            className={classNames(styles.arrowIcon, { [styles.arrowIconActive]: isActive })}
          />
        </div>
        {header}
      </div>
      <div className={styles.contentWrapper} style={{ maxHeight: isActive ? maxHeight : 0 }}>
        <div ref={contentRef} className={classNames(styles.__invalid_content, contentClassName)}>
          {children}
        </div>
      </div>
    </div>
  );
};

export default Collapse;

```

### `src/uikit/DropdownMenu.module.css`

```css
.dropdownMenu {
  background-color: var(--background-primary);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
}

.dropdownMenuItem {
  padding: 6px 8px;
  transition: background-color 0.2s ease;
  cursor: pointer;
  background-color: transparent;
  border: none;
  text-align: left;
  border-bottom: 1px solid var(--divider);
}

.dropdownMenuItem:last-child {
  border-bottom: none;
}

.dropdownMenuItem:hover {
  background-color: var(--link-light-hover);
}

```

### `src/uikit/DropdownMenu.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';

import { Placements } from '../utils/DOMUtils';
import PopoutBase from './PopoutBase';
import Text, { TextWeights } from './Text';

import styles from './DropdownMenu.module.css';

interface BaseMenuOption {
  label: React.ReactNode;
  onClick?: () => void;
}

interface CustomMenuOption<T> {
  label: React.ReactNode;
  onClick?: () => void;
  data: T;
}

export type MenuOption<T = void> = T extends void ? BaseMenuOption : CustomMenuOption<T>;

interface DropdownMenuProps<T = void> {
  children: React.ReactNode;
  options: Array<MenuOption<T>>;
  renderOption?: (option: MenuOption<T>) => React.ReactNode;
  placement?: Placements;
  className?: string;
}

function DropdownMenu<T = void>({ children, options, renderOption, placement, className }: DropdownMenuProps<T>) {
  const [isDropdownVisible, setIsDropdownVisible] = React.useState(false);

  React.useEffect(() => {
    let isOpenClick = true;

    function handleWindowClick() {
      if (isOpenClick) {
        isOpenClick = false;
        return;
      }

      setIsDropdownVisible(false);
    }

    if (isDropdownVisible) {
      window.addEventListener('click', handleWindowClick);
    }

    return () => window.removeEventListener('click', handleWindowClick);
  }, [isDropdownVisible]);

  const handleShowDropdownMenu = () => {
    setIsDropdownVisible(true);
  };

  const renderMenuItem = (option: MenuOption<T>, index: number) => {
    if (renderOption != null) {
      return renderOption(option);
    }

    return (
      <button onClick={option.onClick} className={styles.dropdownMenuItem} key={index}>
        <Text weight={TextWeights.SEMIBOLD}>{option.label}</Text>
      </button>
    );
  };

  const renderDropdownMenu = () => {
    return <div className={classNames(styles.dropdownMenu, className)}>{options.map(renderMenuItem)}</div>;
  };

  return (
    // eslint-disable-next-line
    <span onClick={handleShowDropdownMenu}>
      <PopoutBase
        isVisible={isDropdownVisible}
        content={renderDropdownMenu()}
        placement={placement ?? Placements.BOTTOM_LEFT}
      >
        {children}
      </PopoutBase>
    </span>
  );
}

export default DropdownMenu;

```

### `src/uikit/Expand.module.css`

```css
.expandContainer {
  position: relative;
  transition: max-height 0.25s;
}

.expandable {
  display: block;
  height: 50%;
  width: 100%;
  position: absolute;
  bottom: 0;
  pointer-events: none;
  opacity: 1;
  transition: 0.2s ease-in-out opacity;
}

.expanded.expandable {
  opacity: 0;
}

.expandButton {
  padding: 0;
  height: auto;
  margin: 4px 0;
}

.expandButton:hover {
  background-color: transparent;
}

.remainingRowsPill {
  background-color: var(--background-tertiary);
  border-radius: 4px;
  text-transform: uppercase;
  padding: 2px;
}

```

### `src/uikit/Expand.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';

import OspreyButton, { ButtonColors } from './OspreyButton';
import Text, { TextSizes, TextWeights } from './Text';

import { Colors } from '../Constants';
import styles from './Expand.module.css';

interface ExpandContextT {
  isExpandable: boolean;
  isExpanded: boolean;
  setIsExpandable: (isExpandable: boolean) => void;
  setIsExpanded: (isExpanded?: boolean) => void;
  rowsNotShown: number;
  setRowsNotShown: (rows: number) => void;
}

const ExpandContext = React.createContext<ExpandContextT>({
  isExpandable: false,
  isExpanded: false,
  setIsExpandable: (_isExpandable: boolean) => {},
  setIsExpanded: () => {},
  rowsNotShown: 0,
  setRowsNotShown: (_rows: number) => {},
});

export const ExpandContextProvider = ({ children }: { children: React.ReactNode }) => {
  const [isExpandable, setIsExpandable] = React.useState(false);
  const [isExpanded, setIsExpanded] = React.useState(false);
  const [rowsNotShown, setRowsNotShown] = React.useState(0);

  const handleSetCanExpand = (newCanExpand: boolean) => {
    setIsExpandable(newCanExpand);
  };

  const handleSetIsExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  const handleSetRowsNotShown = (rows: number) => {
    setRowsNotShown(rows);
  };

  return (
    <ExpandContext.Provider
      value={{
        isExpandable,
        isExpanded,
        rowsNotShown,
        setIsExpandable: handleSetCanExpand,
        setIsExpanded: handleSetIsExpanded,
        setRowsNotShown: handleSetRowsNotShown,
      }}
    >
      {children}
    </ExpandContext.Provider>
  );
};

export const ExpandButton = () => {
  const { isExpandable, setIsExpanded, rowsNotShown } = React.useContext(ExpandContext);

  return (
    <>
      {isExpandable ? (
        <OspreyButton className={styles.expandButton} color={ButtonColors.LINK_GRAY} onClick={() => setIsExpanded()}>
          <Text
            size={TextSizes.SMALL}
            weight={TextWeights.SEMIBOLD}
            className={styles.remainingRowsPill}
          >{`+${rowsNotShown} Lines`}</Text>
        </OspreyButton>
      ) : null}
    </>
  );
};

interface ExpandProps {
  children: React.ReactNode;
  className?: string;
  rowHeight?: number;
  fadeColor?: string;
}

const Expand = ({ children, className, rowHeight, fadeColor = Colors.BACKGROUND_SECONDARY_ALT }: ExpandProps) => {
  const { isExpanded, setIsExpandable, isExpandable, setRowsNotShown } = React.useContext(ExpandContext);
  const childNodeHeight: React.MutableRefObject<number | null> = React.useRef(null);

  const childNodeRef = React.useCallback(
    (node: HTMLDivElement | null) => {
      if (node != null) {
        const childNode = node.getBoundingClientRect();
        const parentNode = (node.parentNode as HTMLElement).getBoundingClientRect();
        if (childNode.height > parentNode.height) {
          childNodeHeight.current = childNode.height;
          setIsExpandable(true);

          if (rowHeight != null) {
            const remainingHeight = childNode.height - parentNode.height;
            setRowsNotShown(Math.round(remainingHeight) / rowHeight);
          }
        }
      }
    },
    [rowHeight, setIsExpandable, setRowsNotShown]
  );

  const renderChildNode = () => {
    if (children == null) return null;
    return React.cloneElement(children as React.ReactElement<any>, { ref: childNodeRef });
  };

  const renderGradientOverlay = () => {
    if (!isExpandable) return null;
    return (
      <div
        style={{ backgroundImage: `linear-gradient(to bottom, transparent, ${fadeColor}` }}
        className={classNames(styles.expandable, { [styles.expanded]: isExpanded })}
      />
    );
  };

  const getParentDivStyle = (): React.CSSProperties => {
    if (isExpanded && childNodeHeight.current != null) {
      return { maxHeight: childNodeHeight.current };
    }

    return {};
  };

  /* eslint-disable */
  return (
    <div className={classNames(styles.expandContainer, className)} style={getParentDivStyle()}>
      {renderChildNode()}
      {renderGradientOverlay()}
    </div>
  );
  /* eslint-enable */
};

export default Expand;

```

### `src/uikit/OspreyButton.module.css`

```css
.ospreyButton {
  border-radius: 4px;
  border: none;
  transition: all 0.2s ease-in-out;
  box-shadow: none;
  display: flex;
  justify-content: center;
  align-items: center;
  max-width: 100%;
  user-select: none;
}

.selectable {
  user-select: text;
}

/* Weights */

.normal {
  font-weight: 400 !important;
}

.semibold {
  font-weight: 600 !important;
}

.bold {
  font-weight: 700 !important;
}

/* Colors */

.brand {
  background-color: var(--brand-primary);
  color: var(--text-dark-headings);
}

.brand:hover {
  background-color: var(--brand-dark);
  color: var(--text-dark-headings);
}

.ghost {
  background-color: var(--background-primary);
  color: var(--text-light-secondary);
  border: 1px solid var(--background-tertiary);
}

.ghost:hover {
  background-color: var(--background-secondary);
  color: var(--text-light-primary);
  border: 1px solid var(--divider);
}

.link {
  background-color: transparent;
}

.link:hover {
  background-color: transparent;
}

.linkBrand {
  composes: link;
  color: var(--brand-primary);
}

.linkBrand:hover {
  color: var(--brand-dark);
}

.linkGray {
  composes: link;
  color: var(--text-light-primary);
}

.linkGray:hover {
  color: var(--text-light-headings-primary);
}

.linkDisabled {
  composes: link;
  color: var(--text-light-disabled);
}

.linkDisabled:hover {
  color: var(--text-light-secondary);
}

.linkBlue {
  composes: link;
  color: var(--link-primary);
}

.linkBlue:hover {
  color: var(--link-dark);
}

.dangerRed {
  color: var(--error-primary);
  background-color: var(--error-muted);
  border: 1px solid transparent;
}

.dangerRed:hover {
  background-color: var(--error-muted);
  color: var(--error-primary);
  border: 1px solid var(--error-primary);
}

/* Heights */

.short {
  height: 20px;
  padding: 2px 8px;
}

.default {
  height: 32px;
  padding: 6px 8px;
}

.tall {
  height: 40px;
  padding: 8px 10px;
}

```

### `src/uikit/OspreyButton.tsx`

```typescript
import * as React from 'react';
import { Button } from 'antd';
import type { ButtonProps } from 'antd';
import classNames from 'classnames';

import styles from './OspreyButton.module.css';

export const ButtonColors = {
  DARK_BLUE: styles.brand,
  GHOST: styles.ghost,
  LINK_BRAND: styles.linkBrand,
  LINK_GRAY: styles.linkGray,
  LINK_DISABLED: styles.linkDisabled,
  LINK_BLUE: styles.linkBlue,
  DANGER_RED: styles.dangerRed,
};

export const ButtonHeights = {
  SHORT: styles.short,
  DEFAULT: styles.default,
  TALL: styles.tall,
};

export const ButtonWeights = {
  NORMAL: styles.normal,
  SEMIBOLD: styles.semibold,
  BOLD: styles.bold,
};

interface OspreyButtonProps {
  color?: (typeof ButtonColors)[keyof typeof ButtonColors];
  height?: (typeof ButtonHeights)[keyof typeof ButtonHeights];
  weight?: (typeof ButtonWeights)[keyof typeof ButtonWeights];
  textSelectable?: boolean;
}

const OspreyButton = ({
  className,
  color = ButtonColors.GHOST,
  height = ButtonHeights.DEFAULT,
  weight = ButtonWeights.SEMIBOLD,
  textSelectable = false,
  ...props
}: Omit<ButtonProps, 'color'> & OspreyButtonProps) => {
  return (
    <Button
      className={classNames(
        styles.ospreyButton,
        { [styles.selectable]: textSelectable },
        color,
        height,
        weight,
        className
      )}
      {...props}
    />
  );
};

export default OspreyButton;

```

### `src/uikit/OverflowTooltip.tsx`

```typescript
import * as React from 'react';

import Tooltip, { TooltipSizes, TooltipColors } from './Tooltip';

interface OverflowTooltipProps {
  children: React.ReactNode;
  className?: string;
  tooltipContent: React.ReactNode;
  tooltipClassName?: string;
}

const OverflowTooltip = ({ children, className, tooltipContent, tooltipClassName }: OverflowTooltipProps) => {
  const [showTooltip, setShowTooltip] = React.useState(false);

  const divRef = React.useCallback((node: HTMLElement | null) => {
    if (node != null && node.scrollWidth > node.offsetWidth) {
      setShowTooltip(true);
    }
  }, []);

  return (
    <Tooltip
      className={tooltipClassName}
      content={tooltipContent}
      isDisabled={!showTooltip}
      size={TooltipSizes.SMALL}
      color={TooltipColors.BRAND}
    >
      <div ref={divRef} className={className}>
        {children}
      </div>
    </Tooltip>
  );
};

export default OverflowTooltip;

```

### `src/uikit/PopoutBase.module.css`

```css
.popoutBase {
  position: fixed;
  color: inherit;
  background-color: inherit;
  box-shadow: 0 0 6px 2px var(--background-tertiary);
  border-radius: 4px;
}

.arrow {
  display: block;
  position: absolute;
  background-color: inherit;
  height: 12px;
  width: 12px;
  transform: rotate(225deg);
}

```

### `src/uikit/PopoutBase.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';
import ReactDOM from 'react-dom';

import useResizeObserver from '../hooks/useResizeObserver';
import { getPopoutStyle, Placements } from '../utils/DOMUtils';

import styles from './PopoutBase.module.css';

interface PopoutBaseProps {
  isVisible: boolean;
  content: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  outerClassName?: string;
  useArrow?: boolean;
  placement: Placements;
}

const PopoutBase = ({
  isVisible,
  content,
  children,
  className,
  outerClassName,
  placement,
  useArrow = false,
}: PopoutBaseProps) => {
  const [childNodeBoundingRect, setChildNodeBoundingRect] = React.useState<DOMRect | null>(null);
  const [popoutBaseRef, setPopoutBaseRef] = React.useState<HTMLElement | null>(null);

  const popoutBaseRefCallback = React.useCallback((node: HTMLElement | null) => {
    if (node != null) {
      setPopoutBaseRef(node);
    }
  }, []);
  const childNodeRef = React.useRef<HTMLDivElement>(null);
  const popoutClientRect = useResizeObserver(popoutBaseRef);

  React.useLayoutEffect(() => {
    if (childNodeRef.current == null) return;

    if (isVisible) {
      setChildNodeBoundingRect(childNodeRef.current.getBoundingClientRect());
    } else {
      setChildNodeBoundingRect(null);
    }
    setChildNodeBoundingRect(childNodeRef.current.getBoundingClientRect());
  }, [isVisible]);

  const renderPopoutBaseContent = () => {
    if (childNodeBoundingRect == null) return null;
    const { popoutStyle, arrowStyle } = getPopoutStyle(childNodeBoundingRect, popoutClientRect, placement);

    return (
      <div className={outerClassName} style={{ ...popoutStyle, position: 'absolute', zIndex: 2000 }}>
        <div className={classNames(styles.popoutBase, className)} ref={popoutBaseRefCallback}>
          {content}
        </div>
        {useArrow ? <div className={styles.arrow} style={arrowStyle} /> : null}
      </div>
    );
  };

  const renderPopoutBase = () => {
    if (!isVisible) return null;
    return ReactDOM.createPortal(renderPopoutBaseContent(), document.body);
  };

  return (
    <>
      <div ref={childNodeRef}>{children}</div>
      {renderPopoutBase()}
    </>
  );
};

export default PopoutBase;

```

### `src/uikit/Text.module.css`

```css
/* Headers */

.header {
  color: var(--text-light-headings-primary);
  font-weight: 700;
}

.h1 {
  composes: header;
  font-size: 38px;
  line-height: 46px;
}

.h2 {
  composes: header;
  font-size: 30px;
  line-height: 40px;
}

.h3 {
  composes: header;
  font-size: 24px;
  line-height: 32px;
}

.h4 {
  composes: header;
  font-size: 20px;
  line-height: 28px;
}

.h5 {
  composes: header;
  font-size: 16px;
  line-height: 26px;
}

.h6 {
  composes: header;
  font-size: 14px;
  line-height: 20px;
}

.h7 {
  color: var(--text-light-headings-secondary);
  text-transform: uppercase;
  font-size: 12px;
  line-height: 16px;
  font-weight: 600;
}

/* Body Text Sizes */

.large {
  font-size: 16px;
  line-height: 24px;
}

.small {
  font-size: 12px;
  line-height: 16px;
}

.xsmall {
  font-size: 10px;
  line-height: 16px;
}

/* Styles and Weights */

.italic {
  font-style: italic;
}

.light {
  font-weight: 400;
}

.normal {
  font-weight: 500;
}

.semibold {
  font-weight: 600;
}

.bold {
  font-weight: 700;
}

/* Colors */

.primary {
  color: var(--text-light-primary);
}

.secondary {
  color: var(--text-light-secondary);
}

.lightHeadingsSecondary {
  color: var(--text-light-headings-secondary);
}

.lightHeadingsPrimary {
  color: var(--text-light-headings-primary);
}

.small {
  font-size: 12px;
}

.semibold {
  font-weight: 600;
}

.bold {
  font-weight: 700;
}

.lightPrimary {
  color: var(--text-light-primary);
}

.lightSecondary {
  color: var(--text-light-secondary);
}

.lightDisabled {
  color: var(--text-light-disabled);
}

.linkBlue {
  color: var(--link-primary);
}

```

### `src/uikit/Text.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';

import styles from './Text.module.css';

export const TextSizes = {
  H1: styles.h1,
  H2: styles.h2,
  H3: styles.h3,
  H4: styles.h4,
  H5: styles.h5,
  H6: styles.h6,
  H7: styles.h7,
  LARGE: styles.large,
  SMALL: styles.small,
  NORMAL: styles.normal,
  XSMALL: styles.xsmall,
};

export const TextWeights = {
  LIGHT: styles.light,
  NORMAL: styles.normal,
  SEMIBOLD: styles.semibold,
  BOLD: styles.bold,
};

export const TextColors = {
  LIGHT_PRIMARY: styles.primary,
  LIGHT_SECONDARY: styles.secondary,
  LIGHT_HEADINGS_SECONDARY: styles.lightHeadingsSecondary,
  LIGHT_HEADINGS_PRIMARY: styles.lightHeadingsPrimary,
  LINK_BLUE: styles.linkBlue,
};

interface TextProps {
  children: React.ReactNode;
  className?: string;
  size?: (typeof TextSizes)[keyof typeof TextSizes];
  color?: (typeof TextColors)[keyof typeof TextColors];
  weight?: (typeof TextWeights)[keyof typeof TextWeights];
  italic?: boolean;
  tag?: string | React.ComponentType<React.PropsWithChildren<{ className: string; style?: React.CSSProperties }>>;
}

const Text = ({ children, className, size, color, weight, tag: Tag = 'div', italic = false }: TextProps) => {
  return <Tag className={classNames(size, color, weight, { [styles.italic]: italic }, className)}>{children}</Tag>;
};

export default Text;

```

### `src/uikit/Tooltip.module.css`

```css
.tooltipContent {
  color: inherit;
  background-color: inherit;
  position: relative;
  z-index: 2;
}

.large {
  padding: 16px;
  width: 350px;
  max-height: 500px;
}

.small {
  padding: 8px;
}

.default {
  background-color: var(--background-primary);
}

.brand {
  background-color: var(--brand-primary);
  color: var(--text-dark-headings);
}

```

### `src/uikit/Tooltip.tsx`

```typescript
import * as React from 'react';
import classNames from 'classnames';

import { Placements } from '../utils/DOMUtils';
import PopoutBase from './PopoutBase';

import styles from './Tooltip.module.css';

export const TooltipSizes = {
  SMALL: styles.small,
  LARGE: styles.large,
};

export const TooltipColors = {
  DEFAULT: styles.default,
  BRAND: styles.brand,
};

interface BaseTooltipProps {
  children: React.ReactElement;
  content: React.ReactNode;
  className?: string;
  contentClassName?: string;
  size?: (typeof TooltipSizes)[keyof typeof TooltipSizes];
  color?: (typeof TooltipColors)[keyof typeof TooltipColors];
  placement?: Placements;
  defaultVisible?: boolean;
}

type IsDisabledFunction = (e: React.MouseEvent<HTMLElement>) => boolean;

type TooltipProps = BaseTooltipProps & {
  isDisabled?: boolean | IsDisabledFunction;
};

const Tooltip = ({
  children,
  content,
  isDisabled = false,
  className,
  contentClassName,
  placement = Placements.RIGHT_TOP,
  size = TooltipSizes.LARGE,
  color = TooltipColors.DEFAULT,
  defaultVisible = false,
}: TooltipProps) => {
  const [isTooltipVisible, setIsTooltipVisible] = React.useState(defaultVisible);
  const [isTooltipHovered, setIsTooltipHovered] = React.useState(defaultVisible);

  const isHovered = React.useRef(false);

  React.useEffect(() => {
    let timeoutId: null | NodeJS.Timeout = null;

    if (isTooltipVisible && !isTooltipHovered) {
      timeoutId = setTimeout(() => {
        if (!isHovered.current) {
          setIsTooltipVisible(false);
        }
      }, 150);
    }

    return () => {
      if (timeoutId != null) {
        clearTimeout(timeoutId);
      }
    };
  }, [isTooltipVisible, isTooltipHovered, defaultVisible]);

  const handleShowPopover = (e: React.MouseEvent<HTMLSpanElement>) => {
    if ((typeof isDisabled === 'function' && isDisabled(e)) || (typeof isDisabled === 'boolean' && isDisabled)) return;

    if (!isTooltipVisible) {
      setIsTooltipVisible(true);
    }

    setIsTooltipHovered(true);
    isHovered.current = true;
  };

  const handleHidePopover = () => {
    isHovered.current = false;
    setIsTooltipHovered(false);
  };

  const renderPopoverContent = () => {
    if (!isTooltipVisible) return null;

    return <div className={styles.tooltipContent}>{content}</div>;
  };

  return (
    <span className={contentClassName} onMouseEnter={handleShowPopover} onMouseLeave={handleHidePopover}>
      <PopoutBase
        outerClassName={color}
        className={classNames(size, className)}
        isVisible={isTooltipVisible}
        content={renderPopoverContent()}
        placement={placement}
        useArrow
      >
        {children}
      </PopoutBase>
    </span>
  );
};

export default Tooltip;

```

### `src/uikit/icons/ArrowIcon.tsx`

```typescript
import * as React from 'react';

import { Colors } from '../../Constants';

interface ArrowIconProps {
  width?: number;
  height?: number;
  color?: string;
  className?: string;
}

const ArrowIcon = ({ width = 16, height = 16, color = Colors.ICON_PRIMARY, className }: ArrowIconProps) => {
  return (
    <svg
      className={className}
      width={width}
      height={height}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M4.29504 3.7051L8.87504 8.2951L4.29504 12.8851L5.70504 14.2951L11.705 8.2951L5.70504 2.2951L4.29504 3.7051Z"
        fill={color}
      />
    </svg>
  );
};

export default ArrowIcon;

```

### `src/uikit/icons/BrandDot.tsx`

```typescript
import * as React from 'react';

const BrandDot = ({ className }: { className?: string }) => {
  return (
    <svg className={className} width="6" height="6" viewBox="0 0 6 6" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="3" cy="3" r="3" fill="#1227CE" />
    </svg>
  );
};

export default BrandDot;

```

### `src/uikit/icons/CloseCircleIcon.tsx`

```typescript
import * as React from 'react';

interface CloseCircleIconProps {
  width?: number;
  height?: number;
  className?: string;
}

const CloseCircleIcon = ({ width = 16, height = 16, className }: CloseCircleIconProps) => {
  return (
    <svg
      width={width}
      height={height}
      className={className}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g clipPath="url(#clip0)">
        <path
          d="M8.028 1.33325C4.346 1.33325 1.36133 4.31792 1.36133 7.99992C1.36133 11.6819 4.346 14.6666 8.028 14.6666C11.71 14.6666 14.6947 11.6819 14.6947 7.99992C14.6947 4.31792 11.7093 1.33325 8.028 1.33325ZM11.166 10.1953L10.2233 11.1379L8.028 8.94326L5.83266 11.1379L4.89 10.1953L7.08466 7.99992L4.88933 5.80459L5.832 4.86259L8.02733 7.05792L10.2227 4.86259L11.1653 5.80459L8.97067 7.99992L11.166 10.1953Z"
          fill="#1227CE"
        />
      </g>
      <defs>
        <clipPath id="clip0">
          <rect width="16" height="16" fill="white" />
        </clipPath>
      </defs>
    </svg>
  );
};

export default CloseCircleIcon;

```

### `src/uikit/icons/EventStreamIcon.tsx`

```typescript
import * as React from 'react';

interface EventStreamIconProps {
  width?: number;
  height?: number;
}

const EventStreamIcon = ({ width = 32, height = 32 }: EventStreamIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="16" cy="16" r="16" fill="#CAE0F9" />
      <rect x="9" y="8" width="14" height="6" rx="1" stroke="#1227CE" strokeWidth="2" />
      <rect x="9" y="18" width="14" height="6" rx="1" stroke="#1227CE" strokeWidth="2" />
    </svg>
  );
};

export default EventStreamIcon;

```

### `src/uikit/icons/ExitIcon.tsx`

```typescript
import * as React from 'react';

interface ExitIconProps {
  width?: number;
  height?: number;
}

const ExitIcon = ({ width = 14, height = 14 }: ExitIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M13.304 2.60933L11.418 0.723999L7.02801 5.11467L2.63734 0.723999L0.751343 2.60933L5.14201 7L0.751343 11.3907L2.63734 13.276L7.02801 8.88534L11.418 13.276L13.304 11.3907L8.91335 7L13.304 2.60933Z"
        fill="#535A65"
      />
    </svg>
  );
};

export default ExitIcon;

```

### `src/uikit/icons/ExpandIcon.tsx`

```typescript
import * as React from 'react';

import { Colors } from '../../Constants';

interface ExpandIconProps {
  width?: number;
  height?: number;
  color?: string;
}

const ExpandIcon = ({ width = 16, height = 16, color = Colors.ICON_MUTED }: ExpandIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M19 18C19 18.6 18.6 19 18 19H11V21H18C19.7 21 21 19.7 21 18V11H19V18Z" fill={color} />
      <path d="M5 6C5 5.4 5.4 5 6 5H13V3H6C4.3 3 3 4.3 3 6V13H5V6Z" fill={color} />
      <path d="M15 3V5H17.6L5 17.6V15H3V21H9V19H6.4L19 6.4V9H21V3H15Z" fill={color} />
    </svg>
  );
};

export default ExpandIcon;

```

### `src/uikit/icons/FilterIcon.tsx`

```typescript
import * as React from 'react';

interface FilterIconProps {
  width?: number;
  height?: number;
}

const FilterIcon = ({ width = 32, height = 32 }: FilterIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M13.4713 12.5286L9.87592 8.93331C10.6019 8.00265 10.9999 6.86598 10.9999 5.66665C10.9999 4.24198 10.4446 2.90265 9.43725 1.89598C8.43059 0.88798 7.09125 0.333313 5.66659 0.333313C4.24192 0.333313 2.90259 0.88798 1.89592 1.89598C0.888585 2.90265 0.333252 4.24198 0.333252 5.66665C0.333252 7.09131 0.888585 8.43065 1.89592 9.43731C2.90259 10.4453 4.24192 11 5.66659 11C6.86592 11 8.00259 10.6026 8.93325 9.87598L12.5286 13.4706L13.4713 12.5286ZM5.66659 9.66665C4.59792 9.66665 3.59392 9.25065 2.83859 8.49531C2.08259 7.73998 1.66659 6.73531 1.66659 5.66665C1.66659 4.59865 2.08259 3.59398 2.83859 2.83865C3.59392 2.08265 4.59792 1.66665 5.66659 1.66665C6.73525 1.66665 7.73925 2.08265 8.49459 2.83865C9.25059 3.59398 9.66659 4.59865 9.66659 5.66665C9.66659 6.73531 9.25059 7.73998 8.49459 8.49531C7.73925 9.25065 6.73525 9.66665 5.66659 9.66665Z"
        fill="#9AA1AC"
      />
    </svg>
  );
};

export default FilterIcon;

```

### `src/uikit/icons/FrownyFaceIcon.tsx`

```typescript
import * as React from 'react';

import { Colors } from '../../Constants';

interface FrownyFaceIconProps {
  width?: number;
  height?: number;
  color?: string;
}

const FrownyFaceIcon = ({ width = 14, height = 14, color = Colors.TEXT_LIGHT_PRIMARY }: FrownyFaceIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M7 0C3.1 0 0 3.1 0 7C0 10.9 3.1 14 7 14C10.9 14 14 10.9 14 7C14 3.1 10.9 0 7 0ZM4.5 3C5.3 3 6 3.7 6 4.5C6 5.3 5.3 6 4.5 6C3.7 6 3 5.3 3 4.5C3 3.7 3.7 3 4.5 3ZM3 11C3 8.8 4.8 7 7 7C9.2 7 11 8.8 11 11H3ZM9.5 6C8.7 6 8 5.3 8 4.5C8 3.7 8.7 3 9.5 3C10.3 3 11 3.7 11 4.5C11 5.3 10.3 6 9.5 6Z"
        fill={color}
      />
    </svg>
  );
};

export default FrownyFaceIcon;

```

### `src/uikit/icons/HorizontalMenuIcon.tsx`

```typescript
import * as React from 'react';

import { Colors } from '../../Constants';

interface HorizontalMenuIconProps {
  width?: number;
  height?: number;
  color?: string;
}

const HorizontalMenuIcon = ({ width = 27, height = 24, color = Colors.ICON_MUTED }: HorizontalMenuIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 27 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <g clipPath="url(#clip0)">
        <path
          d="M5.45452 14C6.65951 14 7.63634 13.1046 7.63634 12C7.63634 10.8954 6.65951 10 5.45452 10C4.24954 10 3.27271 10.8954 3.27271 12C3.27271 13.1046 4.24954 14 5.45452 14Z"
          fill={color}
        />
        <path
          d="M13.0909 14C14.2959 14 15.2727 13.1046 15.2727 12C15.2727 10.8954 14.2959 10 13.0909 10C11.8859 10 10.9091 10.8954 10.9091 12C10.9091 13.1046 11.8859 14 13.0909 14Z"
          fill={color}
        />
        <path
          d="M20.7272 14C21.9322 14 22.909 13.1046 22.909 12C22.909 10.8954 21.9322 10 20.7272 10C19.5222 10 18.5454 10.8954 18.5454 12C18.5454 13.1046 19.5222 14 20.7272 14Z"
          fill={color}
        />
      </g>
      <defs>
        <clipPath id="clip0">
          <rect width="26.1818" height={height} fill="white" />
        </clipPath>
      </defs>
    </svg>
  );
};

export default HorizontalMenuIcon;

```

### `src/uikit/icons/ManuallyAddedIcon.tsx`

```typescript
import * as React from 'react';

import { Colors } from '../../Constants';

interface ManuallyAddedIconProps {
  height?: number;
  width?: number;
  color?: string;
  className?: string;
}

const ManuallyAddedIcon = ({
  height = 16,
  width = 20,
  color = Colors.TEXT_LIGHT_PRIMARY,
  className,
}: ManuallyAddedIconProps) => {
  return (
    <svg
      className={className}
      width={width}
      height={height}
      viewBox="0 0 20 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g clipPath="url(#clip0)">
        <path d="M16.51 10.03V7.03H14.51V10.03H11.51V12.03H14.51V15.03H16.51V12.03H19.51V10.03H16.51Z" fill={color} />
        <path
          d="M13.3201 5.26L13.8801 4.7C14.7401 3.84 14.7401 2.45 13.8801 1.59C13.0501 0.759999 11.6001 0.759999 10.7701 1.59L10.2001 2.16L13.3201 5.26Z"
          fill={color}
        />
        <path
          d="M12.3201 6.25999L5.93006 12.65C5.88006 12.7 5.82006 12.75 5.75006 12.78L1.51006 14.9C1.24006 15.04 0.910061 14.98 0.700061 14.77C0.490061 14.56 0.430061 14.23 0.570061 13.96L2.69006 9.71999C2.72006 9.64999 2.77006 9.58999 2.82006 9.53999L9.21006 3.14999L12.3201 6.25999Z"
          fill={color}
        />
      </g>
      <defs>
        <clipPath id="clip0">
          <rect width="19.01" height="14.06" fill="white" transform="translate(0.5 0.970001)" />
        </clipPath>
      </defs>
    </svg>
  );
};

export default ManuallyAddedIcon;

```

### `src/uikit/icons/ManuallyRemovedIcon.tsx`

```typescript
import * as React from 'react';

import { Colors } from '../../Constants';

interface ManuallyRemovedIconProps {
  height?: number;
  width?: number;
  color?: string;
  className?: string;
}

const ManuallyRemovedIcon = ({
  height = 14,
  width = 19,
  color = Colors.TEXT_LIGHT_PRIMARY,
  className,
}: ManuallyRemovedIconProps) => {
  return (
    <svg
      className={className}
      width={width}
      height={height}
      viewBox="0 0 19 14"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g clipPath="url(#clip0)">
        <path
          d="M13.3301 4.29L13.8901 3.73C14.7501 2.87 14.7501 1.48 13.8901 0.619998C13.0601 -0.210002 11.6101 -0.210002 10.7801 0.619998L10.2101 1.19L13.3301 4.29Z"
          fill={color}
        />
        <path
          d="M12.3301 5.28999L5.94007 11.68C5.89007 11.73 5.83007 11.78 5.76007 11.81L1.52007 13.93C1.25007 14.07 0.920071 14.01 0.710071 13.8C0.500071 13.59 0.440071 13.26 0.580071 12.99L2.70007 8.74999C2.73007 8.67999 2.78007 8.61999 2.83007 8.56999L9.22007 2.17999L12.3301 5.28999Z"
          fill={color}
        />
        <path d="M18.66 9.06H12.66V11.06H18.66V9.06Z" fill={color} />
      </g>
      <defs>
        <clipPath id="clip0">
          <rect width="18.15" height="14" fill="white" transform="translate(0.51001)" />
        </clipPath>
      </defs>
    </svg>
  );
};

export default ManuallyRemovedIcon;

```

### `src/uikit/icons/NeutralFaceIcon.tsx`

```typescript
import * as React from 'react';

import { Colors } from '../../Constants';

interface NeutralFaceIconProps {
  width?: number;
  height?: number;
  color?: string;
}

const NeutralFaceIcon = ({ width = 14, height = 14, color = Colors.TEXT_LIGHT_PRIMARY }: NeutralFaceIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M7 0C3.1 0 0 3.1 0 7C0 10.9 3.1 14 7 14C10.9 14 14 10.9 14 7C14 3.1 10.9 0 7 0ZM9.5 3C10.3 3 11 3.7 11 4.5C11 5.3 10.3 6 9.5 6C8.7 6 8 5.3 8 4.5C8 3.7 8.7 3 9.5 3ZM4.5 3C5.3 3 6 3.7 6 4.5C6 5.3 5.3 6 4.5 6C3.7 6 3 5.3 3 4.5C3 3.7 3.7 3 4.5 3ZM3 10C2.44772 10 2 9.55229 2 9C2 8.44771 2.44772 8 3 8H11C11.5523 8 12 8.44771 12 9C12 9.55229 11.5523 10 11 10H3Z"
        fill={color}
      />
    </svg>
  );
};

export default NeutralFaceIcon;

```

### `src/uikit/icons/QueryHistoryIcon.tsx`

```typescript
import * as React from 'react';

interface QueryHistoryIconProps {
  width?: number;
  height?: number;
}

const QueryHistoryIcon = ({ width = 32, height = 32 }: QueryHistoryIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="16" cy="16" r="16" fill="#CAE0F9" />
      <g clipPath="url(#clip0)">
        <path
          d="M21.01 18H20.21L19.94 17.73C20.92 16.59 21.51 15.12 21.51 13.5C21.51 9.91 18.6 7 15.01 7C11.42 7 8.51 10 8.51 13.5H6L9.84 17.5L14 13.5H10.51C10.51 11 12.53 9 15.01 9C17.49 9 19.51 11.01 19.51 13.5C19.51 15.98 17.49 18 15.01 18C14.36 18 13.75 17.86 13.19 17.62L11.71 19.1C12.68 19.67 13.8 20 15.01 20C16.62 20 18.09 19.41 19.23 18.43L19.5 18.7V19.49L24.51 24.48L26 23L21.01 18Z"
          fill="#1227CE"
        />
      </g>
      <defs>
        <clipPath id="clip0">
          <rect width="24" height="24" fill="white" transform="translate(4 4)" />
        </clipPath>
      </defs>
    </svg>
  );
};

export default QueryHistoryIcon;

```

### `src/uikit/icons/QueryIcon.tsx`

```typescript
import * as React from 'react';

interface QueryIconProps {
  width?: number;
  height?: number;
}

const QueryIcon = ({ width = 32, height = 32 }: QueryIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="16" cy="16" r="16" fill="#CAE0F9" />
      <circle cx="14" cy="14" r="8" stroke="#1227CE" strokeWidth="2" />
      <path d="M20.5 20L24.5 24" stroke="#1227CE" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

export default QueryIcon;

```

### `src/uikit/icons/SavedQueriesIcon.tsx`

```typescript
import * as React from 'react';

interface SavedQueriesIconProps {
  width?: number;
  height?: number;
}

const SavedQueriesIcon = ({ width = 32, height = 32 }: SavedQueriesIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M16 32C24.8366 32 32 24.8366 32 16C32 7.16344 24.8366 0 16 0C7.16344 0 0 7.16344 0 16C0 24.8366 7.16344 32 16 32Z"
        fill="#CAE0F9"
      />
      <path
        d="M25.924 12.5865C25.77 12.2126 25.404 11.9681 25 11.9681H19.618L16.894 6.50889C16.555 5.83037 15.444 5.83037 15.105 6.50889L12.382 11.9681H6.99999C6.59599 11.9681 6.22999 12.2126 6.07599 12.5865C5.92199 12.9603 6.00699 13.3933 6.29299 13.6789L10.877 18.2732L9.03899 24.7226C8.92399 25.1265 9.07199 25.5594 9.40999 25.807C9.74999 26.0555 10.207 26.0646 10.554 25.831L16 22.1929L21.445 25.831C21.613 25.9433 21.806 25.9994 22 25.9994C22.207 25.9994 22.414 25.9353 22.59 25.807C22.928 25.5594 23.076 25.1265 22.961 24.7226L21.123 18.2732L25.707 13.6789C25.993 13.3933 26.078 12.9603 25.924 12.5865Z"
        fill="#075DAD"
      />
    </svg>
  );
};

export default SavedQueriesIcon;

```

### `src/uikit/icons/SmileyFaceIcon.tsx`

```typescript
import * as React from 'react';

import { Colors } from '../../Constants';

interface SmileyFaceIconProps {
  width?: number;
  height?: number;
  color?: string;
}

const SmileyFaceIcon = ({ width = 14, height = 14, color = Colors.TEXT_LIGHT_PRIMARY }: SmileyFaceIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M7 0C3.1 0 0 3.1 0 7C0 10.9 3.1 14 7 14C10.9 14 14 10.9 14 7C14 3.1 10.9 0 7 0ZM9.5 3C10.3 3 11 3.7 11 4.5C11 5.3 10.3 6 9.5 6C8.7 6 8 5.3 8 4.5C8 3.7 8.7 3 9.5 3ZM4.5 3C5.3 3 6 3.7 6 4.5C6 5.3 5.3 6 4.5 6C3.7 6 3 5.3 3 4.5C3 3.7 3.7 3 4.5 3ZM7 12C4.2 12 2 9.8 2 7H12C12 9.8 9.8 12 7 12Z"
        fill={color}
      />
    </svg>
  );
};

export default SmileyFaceIcon;

```

### `src/uikit/icons/StarIcon.tsx`

```typescript
import * as React from 'react';

import { Colors } from '../../Constants';

interface StarIconProps {
  width?: number;
  height?: number;
  color?: string;
}

const StarIcon = ({ width = 12, height = 12, color = Colors.ICON_PRIMARY }: StarIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M6.66225 0.513353L7.68895 3.76459H11.1113C11.8813 3.76459 12.138 4.70573 11.5391 5.13353L8.71566 7.18694L9.74236 10.4382C9.99904 11.1226 9.14345 11.7215 8.54454 11.2938L5.97778 9.3259L3.15434 11.3793C2.55543 11.8071 1.7854 11.2082 1.95652 10.5237L2.98322 7.27249L0.330901 5.13353C-0.26801 4.70573 -0.0113338 3.76459 0.758695 3.76459H4.18105L5.20775 0.513353C5.46443 -0.171118 6.49113 -0.171118 6.66225 0.513353Z"
        fill={color}
      />
    </svg>
  );
};

export default StarIcon;

```

### `src/uikit/icons/TimeseriesIcon.tsx`

```typescript
import * as React from 'react';

interface TimeseriesIconProps {
  width?: number;
  height?: number;
}

const TimeseriesIcon = ({ width = 32, height = 32 }: TimeseriesIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M16 32C24.8366 32 32 24.8366 32 16C32 7.16344 24.8366 0 16 0C7.16344 0 0 7.16344 0 16C0 24.8366 7.16344 32 16 32Z"
        fill="#CAE0F9"
      />
      <path
        d="M6 23L8.6 19.1C9.3 18 10.9 17.9 11.8 18.8L12.2 19.2C13.1 20.1 14.7 20 15.4 18.9L16.6 17.1C17.3 16 18.9 15.9 19.8 16.8C20.8 17.8 22.6 17.5 23.2 16.1L26 9"
        stroke="#1227CE"
        strokeWidth="2"
        strokeMiterlimit="10"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

export default TimeseriesIcon;

```

### `src/uikit/icons/TopNIcon.tsx`

```typescript
import * as React from 'react';

interface TopNIconProps {
  width?: number;
  height?: number;
}

const TopNIcon = ({ width = 32, height = 32 }: TopNIconProps) => {
  return (
    <svg width={width} height={height} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="16" cy="16" r="16" fill="#CAE0F9" />
      <rect x="7" y="9" width="18" height="2" rx="1" fill="#1227CE" />
      <rect x="7" y="15" width="14" height="2" rx="1" fill="#1227CE" />
      <rect x="7" y="21" width="10" height="2" rx="1" fill="#1227CE" />
    </svg>
  );
};

export default TopNIcon;

```

### `src/utils/AutoCompleteUtils.tsx`

```typescript
import { OptionData, OptionGroupData } from 'rc-select/lib/interface/index';

import useApplicationConfigStore from '../stores/ApplicationConfigStore';

const actionNameComparisonRegEx = /ActionName\s?(=|!)=\s['"]?[a-z_]*?$/;
const actionNameLookupRegEx = /[a-z_]*$/;

export const filterAutoComplete = (inputValue: string, option?: OptionData | OptionGroupData): boolean => {
  if (option == null) return false;
  const { knownActionNames } = useApplicationConfigStore.getState();
  const optionString = String(option.value);

  const isAnActionNameComparison = actionNameComparisonRegEx.test(inputValue);
  const optionIsAnActionName = knownActionNames.has(optionString);

  if (isAnActionNameComparison && optionIsAnActionName) {
    const actionNameLookupMatch = actionNameLookupRegEx.exec(inputValue);
    if (actionNameLookupMatch == null) return false;

    const actionNameLookupString = actionNameLookupMatch[0];
    return optionString.includes(actionNameLookupString);
  } else if (isAnActionNameComparison || optionIsAnActionName) {
    return false;
  }

  const currentWord = String(inputValue.split(' ').slice(-1));
  return optionString.toUpperCase().includes(currentWord.toUpperCase());
};

export const sortOptions = (inputValue: string) => {
  const upperInput = inputValue.toUpperCase();
  return (a: OptionData, b: OptionData) => {
    const upperA = String(a.value).toUpperCase();
    const upperB = String(b.value).toUpperCase();

    const isExactA = upperA === upperInput ? 0 : 1;
    const isExactB = upperB === upperInput ? 0 : 1;

    const startsWithA = upperA.startsWith(upperInput) ? 0 : 1;
    const startsWithB = upperB.startsWith(upperInput) ? 0 : 1;

    return isExactA - isExactB || startsWithA - startsWithB || upperA.localeCompare(upperB);
  };
};

```

### `src/utils/DOMUtils.tsx`

```typescript
import { CSSProperties } from 'react';

const MARGIN = 12;
const ARROW_ICON_SPACING = 6;
const ARROW_ICON_SIZE = 12;
// The arrow icon is actually a diamond, only 2px of it should be peeping out from behind a tooltip.
const ARROW_ICON_SHOWN = 2;

export enum Placements {
  RIGHT_TOP = 'RIGHT_TOP',
  RIGHT_BOTTOM = 'RIGHT_BOTTOM',
  LEFT_TOP = 'LEFT_TOP',
  LEFT_BOTTOM = 'LEFT_BOTTOM',
  TOP_LEFT = 'TOP_LEFT',
  TOP_RIGHT = 'TOP_RIGHT',
  BOTTOM_LEFT = 'BOTTOM_LEFT',
  BOTTOM_RIGHT = 'BOTTOM_RIGHT',
}

enum Position {
  TOP = 'TOP',
  BOTTOM = 'BOTTOM',
  LEFT = 'LEFT',
  RIGHT = 'RIGHT',
}

enum Align {
  TOP = 'TOP',
  BOTTOM = 'BOTTOM',
  LEFT = 'LEFT',
  RIGHT = 'RIGHT',
}

const PlacementProps: Record<Position, 'top' | 'left'> = {
  [Position.TOP]: 'top',
  [Position.BOTTOM]: 'top',
  [Position.LEFT]: 'left',
  [Position.RIGHT]: 'left',
};

const PlacementDimensions: Record<Position, 'height' | 'width'> = {
  [Position.TOP]: 'height',
  [Position.BOTTOM]: 'height',
  [Position.LEFT]: 'width',
  [Position.RIGHT]: 'width',
};

function _getCorrected<T>(current: T, incorrect: T, alternate: T): T {
  return current === incorrect ? alternate : current;
}

function _getValuesFromPlacement(placement: Placements): { position: Position; align: Align } {
  const [positionStr, alignStr] = placement.split('_');
  const position = Position[positionStr as Position];
  const align = Align[alignStr as Align];

  return { position, align };
}

function _fitPopoutToWindow(
  popoutClientRect: DOMRect,
  popoutStyle: CSSProperties,
  { position, align }: { position: Position; align: Align }
): Placements {
  let correctedPosition = position;
  let correctedAlign = align;

  const left = popoutStyle.left != null ? Number(popoutStyle.left) : 0;
  const top = popoutStyle.top != null ? Number(popoutStyle.top) : 0;

  const isTooFarRight = left + popoutClientRect.width > window.innerWidth;
  const isTooFarTop = top < 0;
  const isTooFarLeft = left < 0;
  const isTooFarBottom = top + popoutClientRect.height > window.innerHeight;

  if (isTooFarTop) {
    correctedPosition = _getCorrected(position, Position.TOP, Position.BOTTOM);
    correctedAlign = _getCorrected(align, Align.BOTTOM, Align.TOP);
  } else if (isTooFarBottom) {
    correctedPosition = _getCorrected(position, Position.BOTTOM, Position.TOP);
    correctedAlign = _getCorrected(align, Align.TOP, Align.BOTTOM);
  }

  if (isTooFarLeft) {
    correctedPosition = _getCorrected(correctedPosition, Position.LEFT, Position.RIGHT);
    correctedAlign = _getCorrected(correctedAlign, Align.RIGHT, Align.LEFT);
  } else if (isTooFarRight) {
    correctedPosition = _getCorrected(correctedPosition, Position.RIGHT, Position.LEFT);
    correctedAlign = _getCorrected(correctedAlign, Align.LEFT, Align.RIGHT);
  }

  const newPlacement = `${correctedPosition}_${correctedAlign}`;
  return newPlacement as Placements;
}

export function getPopoutStyle(
  clientRect: DOMRect,
  popoutClientRect: DOMRect | null,
  placement: Placements = Placements.RIGHT_BOTTOM,
  isCorrected: boolean = false
): { popoutStyle: React.CSSProperties; arrowStyle: React.CSSProperties } {
  const popoutStyle: React.CSSProperties = {};
  const arrowStyle: React.CSSProperties = {};
  if (popoutClientRect == null) return { popoutStyle, arrowStyle };
  const { position, align } = _getValuesFromPlacement(placement);

  const posProp = PlacementProps[position];
  const alignProp = PlacementProps[align];

  const posDim = PlacementDimensions[position];
  const alignDim = PlacementDimensions[align];

  if (position === Position.TOP || position === Position.LEFT) {
    popoutStyle[posProp] = clientRect[posProp] - popoutClientRect[posDim] - MARGIN;
    arrowStyle[posProp] = popoutClientRect[posDim] - ARROW_ICON_SIZE + ARROW_ICON_SHOWN;
  } else {
    popoutStyle[posProp] = clientRect[posProp] + clientRect[posDim] + MARGIN;
    arrowStyle[posProp] = -ARROW_ICON_SHOWN;
  }

  if (align === Align.TOP || align === Align.LEFT) {
    popoutStyle[alignProp] = clientRect[alignProp];
    arrowStyle[alignProp] = ARROW_ICON_SPACING;
  } else {
    popoutStyle[alignProp] = clientRect[alignProp] + clientRect[alignDim] - popoutClientRect[alignDim];
    arrowStyle[alignProp] = popoutClientRect[alignDim] - ARROW_ICON_SPACING - ARROW_ICON_SIZE;
  }

  if (!isCorrected) {
    const correctedPlacement = _fitPopoutToWindow(popoutClientRect, popoutStyle, { position, align });
    return getPopoutStyle(clientRect, popoutClientRect, correctedPlacement, true);
  }

  popoutStyle.width = popoutClientRect.width;
  return { popoutStyle, arrowStyle };
}

```

### `src/utils/DateUtils.tsx`

```typescript
import dayjs, { type Dayjs, type ManipulateType } from 'dayjs';

import { IntervalOptions, MomentRangeValues } from '../types/QueryTypes';

import { DATE_FORMAT } from '../Constants';

const DURATIONS: readonly ManipulateType[] = ['month', 'week', 'day', 'hour'];

export function formatUtcTimestamp(timestamp: string | Dayjs): string {
  return dayjs.utc(timestamp).format(DATE_FORMAT);
}

export function localizeAndFormatTimestamp(timestamp: string | Dayjs): string {
  return dayjs.utc(timestamp).tz(dayjs.tz.guess()).format(DATE_FORMAT);
}

export function isTimestampPast(timestamp: string): boolean {
  return dayjs.utc(timestamp).isBefore(dayjs.utc());
}

export function getIntervalFromDateRange({ start, end }: { start: string; end: string }): MomentRangeValues | null {
  const dayjsDuration = dayjs.duration(dayjs(start).diff(dayjs(end)));
  let unit: ManipulateType | null = null;
  let numUnits = 0;

  for (const timeUnit of DURATIONS) {
    const num = Math.abs(dayjsDuration.as(timeUnit));
    if (num % 1 === 0) {
      unit = timeUnit;
      numUnits = num;
      break;
    }
  }

  if (unit == null) return null;

  const intervalOption = Object.keys(IntervalOptions).find((key) => {
    const { durationConstructor: option } = IntervalOptions[key as MomentRangeValues];
    return option[0] === numUnits && option[1] === unit;
  });

  return (intervalOption as MomentRangeValues) ?? null;
}

```

### `src/utils/DayjsSetup.tsx`

```typescript
import dayjs from 'dayjs';
import customParseFormat from 'dayjs/plugin/customParseFormat';
import duration from 'dayjs/plugin/duration';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(duration);
dayjs.extend(customParseFormat);

```

### `src/utils/EntityUtils.tsx`

```typescript
import * as React from 'react';

import Feature from '../components/common/Feature';
import EntityWithPopover from '../components/entities/EntityWithPopover';
import useApplicationConfigStore, { LabelInfoMapping } from '../stores/ApplicationConfigStore';
import { SortedLabels, Label, LabelConnotation } from '../types/LabelTypes';
import { FeatureLocation } from '../types/ConfigTypes';
import EntityNameWithPopover from '../components/entities/EntityNameWithPopover';
import FeatureName from '../components/common/FeatureName';

export function wrapEntityKeysWithFeatureLocationsMenu(
  featureName: string,
  featureLocations: Array<FeatureLocation> | undefined
) {
  const location = featureLocations?.find((location) => location.name === featureName);

  return <EntityNameWithPopover name={featureName} location={location} />;
}

export function wrapEntityValuesWithLabelMenu(value: unknown, featureName: string) {
  if (value == null) {
    return <Feature featureName={featureName} value={null} />;
  }

  const { featureNameToEntityTypeMapping } = useApplicationConfigStore.getState();
  const entityType = featureNameToEntityTypeMapping.get(featureName);

  return entityType != null ? (
    <EntityWithPopover featureName={featureName} entityId={String(value)} entityType={entityType} />
  ) : (
    <Feature featureName={featureName} value={value} />
  );
}

export function sortLabels(labels: Label[], labelInfoMapping: LabelInfoMapping): SortedLabels {
  const sortedLabels: SortedLabels = { positive: [], negative: [], neutral: [] };

  for (const label of labels) {
    const connotation: LabelConnotation = labelInfoMapping.get(label.name)?.connotation ?? LabelConnotation.NEUTRAL;
    sortedLabels[connotation].push(label);
  }

  return sortedLabels;
}

```

### `src/utils/ErrorReporting.tsx`

```typescript
import * as Sentry from '@sentry/browser';

if (process.env.REACT_APP_SENTRY_DSN) {
  Sentry.init({ dsn: process.env.REACT_APP_SENTRY_DSN });
}

```

### `src/utils/EventListenerUtils.tsx`

```typescript
import useApplicationConfigStore from '../stores/ApplicationConfigStore';
import useQueryStore from '../stores/QueryStore';
import { addFeaturesToQueryFilter } from './QueryUtils';
import { openNewQueryWindow } from './SearchParamUtils';

export function startRecordingClicks(e: KeyboardEvent) {
  if (e.key === 'Shift') {
    useApplicationConfigStore.setState({ isRecordingClicks: true });
  }
}

export function stopRecordingClicks(e: KeyboardEvent) {
  if (e.key !== 'Shift') return;
  const { executedQuery, queuedQueryFilters, updateExecutedQuery, updateQueuedQueryFilters } = useQueryStore.getState();

  if (queuedQueryFilters.length > 0) {
    const updatedFilter = addFeaturesToQueryFilter(queuedQueryFilters, executedQuery.queryFilter);
    if (e.ctrlKey || e.metaKey) {
      openNewQueryWindow(updatedFilter);
    } else {
      updateExecutedQuery({ ...executedQuery, queryFilter: updatedFilter });
    }

    updateQueuedQueryFilters([]);
  }

  useApplicationConfigStore.setState({ isRecordingClicks: false });
}

```

### `src/utils/HTTPUtils.tsx`

```typescript
import axios, { AxiosError, AxiosResponse } from 'axios';

import useErrorStore from '../stores/ErrorStore';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL;
const CORS_HEADER = { 'Access-Control-Allow-Origin': '*' };

const axiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: CORS_HEADER,
});

export type HTTPResponse = (AxiosResponse & { ok: true }) | { ok: false; error: AxiosError<any> };

const errorHandler = (error: AxiosError<any>): HTTPResponse => {
  if (error.response != null) {
    const { errors } = useErrorStore.getState();
    useErrorStore.setState({ errors: new Set([...errors, error.response.data]) });
  }

  return { ok: false, error };
};

axiosInstance.interceptors.response.use((response) => ({ ...response, ok: true }), errorHandler);

export default axiosInstance;

```

### `src/utils/LabelUtils.tsx`

```typescript
import { Label } from '../types/LabelTypes';

export function sortLabelsChronologically(labels: Label[]) {
  const labelsByLatestTimestamp: Array<[string, Label]> = labels.map((label) => {
    let latestTimestamp: string = '';

    Object.values(label.reasons).forEach((reason) => {
      if (latestTimestamp === '' || Date.parse(reason.created_at) - Date.parse(latestTimestamp) > 0) {
        latestTimestamp = reason.created_at;
      }
    });

    return [latestTimestamp, label];
  });

  const sortedLabels = labelsByLatestTimestamp
    .sort(([timestampA], [timestampB]) => Date.parse(timestampB) - Date.parse(timestampA))
    .map(([_, label]) => label);

  return sortedLabels;
}

```

### `src/utils/PromiseResultUtils.tsx`

```typescript
import * as React from 'react';
import { ReloadOutlined } from '@ant-design/icons';
import { Spin, Alert, Button } from 'antd';
import { sample } from 'lodash';

import { PromiseResult, PromiseResultStatus } from '../hooks/usePromiseResult';

interface RenderResolvedPromiseOptions {
  // A custom function that will render a specific "resolving" state, rather than the default loading UI.
  renderResolving?: () => React.ReactElement | null;
  // A custom function that will render a specific "rejected" state, rather than the default rejection UI.
  renderRejected?: (error: Error, retry: () => void) => React.ReactElement;

  showStackTrace?: boolean;
}

const loadingLines = [
  'Upsorbing the Contents',
  'Additive Parsing the Load',
  'Commence Monosaturated Goodening',
  'Kick Off the Multi-Core Widening',
  'Bastening the Game Turkey',
  'Abstracting the Rummage Disc',
  'Undecerealenizing the Process',
  'Postrefragmenting the Widget Layer',
  'Satisfying the Constraints',
  'Abnoramalzing Some of the Matrices',
  'Optimizing the People',
  'Proclaigerizing the Network',
];

function Resolving() {
  const loadingLine = React.useMemo(() => sample(loadingLines), []);
  return (
    <Spin tip={loadingLine} size="large">
      <div style={{ height: '100px' }} />
    </Spin>
  );
}

function Rejected({ error, retry, showStackTrace }: { error: Error; retry: () => void; showStackTrace: boolean }) {
  // Sanitize the stack trace a bit better, by stripping the first line (which will usually be Error: ${error.message})
  const stackTrace =
    showStackTrace && error.stack ? (
      <pre>
        {error.stack
          .split('\n')
          .slice(1)
          .map((l) => l.trim())
          .join('\n')}
      </pre>
    ) : null;

  const description = (
    <>
      {stackTrace}
      <Button icon={<ReloadOutlined />} size="middle" onClick={retry}>
        Retry
      </Button>
    </>
  );

  return <Alert message={<code>{error.message}</code>} description={description} type="error" showIcon />;
}

export function renderFromPromiseResult<T>(
  promiseResult: PromiseResult<T>,
  renderResolved: (resolved: T) => React.ReactElement,
  options: RenderResolvedPromiseOptions = {}
): React.ReactElement | null {
  switch (promiseResult.status) {
    case PromiseResultStatus.Resolving:
      return options.renderResolving?.() ?? <Resolving />;
    case PromiseResultStatus.Resolved:
      return renderResolved(promiseResult.value);
    case PromiseResultStatus.Rejected:
      const { error, retry } = promiseResult;
      return (
        options.renderRejected?.(error, retry) ?? (
          <Rejected error={error} retry={retry} showStackTrace={options.showStackTrace ?? true} />
        )
      );
  }
}

```

### `src/utils/QueryStoreUtils.tsx`

```typescript
import { History, Location } from 'history';
import { matchPath } from 'react-router-dom';

import { saveQueryToHistory } from '../actions/QueryActions';
import {
  BaseQuery,
  DefaultIntervals,
  QueryState,
  CustomSummaryFeatures,
  ScanQueryOrder,
  MomentRangeValues,
  TopNTable,
  Chart,
} from '../types/QueryTypes';
import { getQueryDateRange, isEmptyDateRange } from './QueryUtils';

import { Routes } from '../Constants';

type QueryStoreState = QueryState & {
  customSummaryFeatures: CustomSummaryFeatures;
  entityFeatureFilters: Set<string>;
};

export function extractQueryStateFromSearchParams(location: Location): QueryStoreState {
  const isEntityView = matchPath(location.pathname, { path: Routes.ENTITY }) != null;
  const queryString = new URLSearchParams(location.search);

  const topNTables: Map<string, TopNTable> = new Map();
  queryString.getAll('topn').map((data) => {
    const table: TopNTable = TopNTable.fromQueryParam(data);
    topNTables.set(table.dimension, table);
  });

  const charts: Array<Chart> = queryString.getAll('chart').map(Chart.fromQueryParam);

  const customSummaryFeatures = queryString.getAll('customSummaryFeatures');

  const queryState = {
    executedQuery: {
      queryFilter: queryString.get('queryFilter') || '',
      start: queryString.get('start') || '',
      end: queryString.get('end') || '',
      interval:
        queryString.get('interval') != null && queryString.get('interval') !== ''
          ? (queryString.get('interval') as DefaultIntervals)
          : 'day',
    },
    // Parse a `ScanQueryOrder` from the query string, defaulting to `descending` if the order isn't understood or
    // not provided.
    sortOrder:
      queryString.get('order') === ScanQueryOrder.ASCENDING ? ScanQueryOrder.ASCENDING : ScanQueryOrder.DESCENDING,
    topNTables,
    charts,
    entityFeatureFilters: new Set(queryString.getAll('entityFeatureFilters')),
    customSummaryFeatures: customSummaryFeatures.length === 0 ? null : customSummaryFeatures,
  };

  const { start, end } = queryState.executedQuery;

  // Do not save queries from the entity view yet
  if (!isEntityView && !isEmptyDateRange(start, end)) {
    saveQueryToHistory(queryState);
  }

  return queryState;
}

export function getSearchParamsForExecutedQuery(query: BaseQuery, location?: Location): URLSearchParams {
  const queryString = new URLSearchParams(location?.search ?? '');

  Object.entries(query).forEach(([key, value]) => {
    if (value != null) {
      queryString.set(key, String(value));
    }
  });

  return queryString;
}

const ENTITY_VIEW_DEFAULT_SEARCH_PARAMS: Array<[string, string]> = [
  ['queryFilter', ''],
  ['topn', 'ActionName'],
];
const ENTITY_VIEW_DEFAULT_INTERVAL: MomentRangeValues = 'twoWeeks';

export function setSearchParamsForEntityView(history: History) {
  // Check that we are acting on the correct route.
  const entityViewMatch = matchPath(history.location.pathname, { path: Routes.ENTITY });
  if (entityViewMatch == null) {
    return;
  }

  const locationSearchParams = new URLSearchParams(history.location.search);

  // If not all location based params are set, choose a default of last two weeks.
  if (!['start', 'end', 'interval'].every((param) => locationSearchParams.has(param))) {
    const { start, end } = getQueryDateRange(ENTITY_VIEW_DEFAULT_INTERVAL);
    locationSearchParams.set('start', start);
    locationSearchParams.set('end', end);
    locationSearchParams.set('interval', ENTITY_VIEW_DEFAULT_INTERVAL);
  }

  // Ensure all defaults are set.
  for (const [key, value] of ENTITY_VIEW_DEFAULT_SEARCH_PARAMS) {
    if (!locationSearchParams.has(key)) {
      locationSearchParams.set(key, value);
    }
  }

  history.replace({ pathname: history.location.pathname, search: `?${locationSearchParams}` });
}

```

### `src/utils/QueryUtils.tsx`

```typescript
import { isEqual } from 'lodash';
import dayjs from 'dayjs';

import useApplicationConfigStore from '../stores/ApplicationConfigStore';
import { Feature } from '../types/EntityTypes';
import { DefaultIntervals, IntervalOptions, BaseQuery, TopNTable, QueryState } from '../types/QueryTypes';
export const CUSTOM_RANGE_OPTION = 'custom';

export function isEmptyDateRange(start: string, end: string): boolean {
  return start === '' || end === '';
}

export function getQueryDateRange(
  interval: DefaultIntervals,
  dateRange: { start: string; end: string } = { start: '', end: '' }
): { start: string; end: string } {
  if (interval == null) {
    throw new Error('Default range cannot be null');
  }

  if (interval !== CUSTOM_RANGE_OPTION) {
    const {
      durationConstructor: [amount, unit],
    } = IntervalOptions[interval];

    return {
      start: dayjs.utc().subtract(amount, unit).format(),
      end: dayjs.utc().format(),
    };
  }

  const { start, end } = dateRange;

  if (isEmptyDateRange(start, end)) {
    throw new Error('Date range must be specified when using custom interval');
  }

  return { start, end };
}

/**
 * This attempts to format/render a value based on the string representation of types that the server sends down.
 * This representation is defined in api, but briefly looks like:
 *
 * - The string value 'str', 'int', 'float', or 'bool' for scalar types
 * - A '?' suffix for optional types
 * - A 'list<...>' prefix/suffix for list types
 *
 * Note that this is incomplete (namely does not handle list types currently) and falls back to just leaving the value
 * as is if the type is unknown.
 */
const renderValueWithType = (value: string | null, type: string | undefined): string => {
  if (value == null) {
    return 'None';
  }

  if (type !== undefined) {
    if (type.endsWith('?')) {
      if (value === 'null') {
        return 'None';
      } else {
        return renderValueWithType(value, type.slice(0, type.length - 1));
      }
    } else if (type === 'str') {
      const escapedId = value.replace(`'`, `\\'`);
      return `'${escapedId}'`;
    } else if (type === 'int' || type === 'float') {
      return value;
    } else if (type === 'bool') {
      if (value === 'true') {
        return 'True';
      } else if (value === 'false') {
        return 'False';
      }
    }
  }

  // Best effort, just return the thing.
  // TODO - Better system for warning that we have an unknown type?
  console.warn(`Unknown feature value type '${type}'!`); // eslint-disable-line no-console
  return value;
};

export function addFeaturesToQueryFilter(featureAdditions: Feature[], queryFilter: string = ''): string {
  const { featureNameToValueTypeMapping } = useApplicationConfigStore.getState();

  const groupedByFeatureName = featureAdditions.reduce<{ [key: string]: Array<string | null> }>(
    (groupedAdditions, addition) => {
      if (Object.prototype.hasOwnProperty.call(groupedAdditions, addition.featureName)) {
        groupedAdditions[addition.featureName].push(addition.value);
      } else {
        groupedAdditions[addition.featureName] = [addition.value];
      }
      return groupedAdditions;
    },
    {}
  );

  const additions = Object.entries(groupedByFeatureName).reduce((newQueryFilter, [featureName, featureIds]) => {
    let newFilter = '';
    const featureIdType = featureNameToValueTypeMapping.get(featureName);
    const renderedIds = featureIds.map((id) => renderValueWithType(id, featureIdType));

    if (renderedIds.length > 1) {
      newFilter = `${featureName} in [${renderedIds.join(', ')}]`;
    } else {
      newFilter = `${featureName} == ${renderedIds[0]}`;
    }

    const addition = newQueryFilter === '' ? newFilter : ` and ${newFilter}`;
    return newQueryFilter + addition;
  }, '');

  return queryFilter === '' ? additions : queryFilter + ` and ${additions}`;
}

export function baseQueryEquals(a: BaseQuery, b: BaseQuery): boolean {
  return (
    dayjs(a.start).isSame(b.start) &&
    dayjs(a.end).isSame(b.end) &&
    a.interval === b.interval &&
    a.queryFilter === b.queryFilter
  );
}

export function topNEquals(a: Map<string, TopNTable>, b: Map<string, TopNTable>): boolean {
  return a.size === b.size && isEqual(a, b);
}

export function queryStateEquals(a: QueryState, b: QueryState): boolean {
  return (
    baseQueryEquals(a.executedQuery, b.executedQuery) &&
    topNEquals(a.topNTables, b.topNTables) &&
    a.sortOrder === b.sortOrder
  );
}

```

### `src/utils/RouteUtils.tsx`

```typescript
import { Entity } from '../types/EntityTypes';
import { SavedQuery } from '../types/QueryTypes';

export function makeEntityRoute(entity: Entity): string {
  return `/entity/${encodeURIComponent(entity.type)}/${encodeURIComponent(entity.id)}`;
}

export function makeSavedQueryRoute(savedQuery: SavedQuery): string {
  return `/saved-query/${savedQuery.id}`;
}

export function makeLatestSavedQueryRoute(savedQuery: SavedQuery): string {
  return `/saved-query/${savedQuery.id}/latest`;
}

```

### `src/utils/SearchParamUtils.tsx`

```typescript
import dayjs from 'dayjs';

import { history } from '../stores/QueryStore';
import { QueryRecord, ScanQueryOrder } from '../types/QueryTypes';
import { getIntervalFromDateRange } from './DateUtils';
import { getQueryDateRange } from './QueryUtils';

export function openNewQueryWindow(queryFilter: string) {
  const queryString = new URLSearchParams(history.location.search);
  queryString.set('queryFilter', queryFilter);

  window.open(`${window.location.origin}/?${queryString.toString()}`, window.name);
}

export function getSearchParamsForQueryRecord(query: QueryRecord, useInterval: boolean = false): string {
  const interval = getIntervalFromDateRange(query.date_range);

  let start = dayjs.utc(query.date_range.start).format();
  let end = dayjs.utc(query.date_range.end).format();

  if (useInterval && interval != null) {
    const dateRange = getQueryDateRange(interval);

    start = dateRange.start;
    end = dateRange.end;
  }

  const queryString = new URLSearchParams();
  queryString.append('queryFilter', query.query_filter);
  queryString.append('start', start);
  queryString.append('end', end);

  if (interval != null) {
    queryString.append('interval', interval);
  }

  if (query.sort_order === ScanQueryOrder.ASCENDING) {
    queryString.append('sortOrder', ScanQueryOrder.ASCENDING);
  }

  if (query.top_n.length > 0) {
    query.top_n.forEach((table) => {
      queryString.append('topn', table.asQueryParam());
    });
  }

  return `?${queryString.toString()}`;
}

```

### `src/utils/SourceUtils.tsx`

```typescript
const GITHUB_REPO_URL = 'https://github.com/roostorg/osprey/tree/main/example_rules';

export function getSourcesUrl({ path, lineNumber }: PathInfo): string {
  return `${GITHUB_REPO_URL}${path}#L${lineNumber}`;
}

export interface PathInfo {
  path: string;
  lineNumber: number;
  rest: string;
}

export function parsePathString(path: string): PathInfo | null {
  const match = /^(.*?):(\d+)(.*)$/.exec(path);
  if (match == null) {
    return null;
  }

  return {
    path: match[1],
    lineNumber: +match[2],
    rest: match[3],
  };
}

```

### `src/utils/StringUtils.tsx`

```typescript
export function pluralize(word: string, val: number, pluralization: string = 's'): string {
  if (val === 1) return word;

  return `${word}${pluralization}`;
}

/**
 * Splits a string into an array of objects containing substrings and their match status.
 * Supports both exact string matching and regex patterns. Matched substrings are included in the result.
 * Useful for tokenizing a string so that substrings matching a search query can be highlighted.
 *
 * @param str - The string to split
 * @param pattern - The substring or regex pattern to match against
 * @param useRegex - Whether to treat the pattern as a regex (default: false)
 * @returns Array of objects with substring and matched properties
 * @throws {Error} When useRegex is true and pattern is an invalid regex
 *
 * @example
 * ```ts
 * // Exact string matching
 * const result1 = splitStringIncludingMatches("foo boor", "oo");
 * // returns [
 * //   { substring: "f", matched: false },
 * //   { substring: "oo", matched: true },
 * //   { substring: " b", matched: false },
 * //   { substring: "oo", matched: true },
 * //   { substring: "r", matched: false }
 * // ]
 *
 * // Regex matching
 * const result2 = splitStringIncludingMatches("foo123bar456", "\\d+", true);
 * // returns [
 * //   { substring: "foo", matched: false },
 * //   { substring: "123", matched: true },
 * //   { substring: "bar", matched: false },
 * //   { substring: "456", matched: true }
 * // ]
 * ```
 */
export function splitStringIncludingMatches(
  str: string,
  pattern: string,
  useRegex: boolean = false
): Array<{ substring: string; matched: boolean }> {
  // Early returns for edge cases
  if (!str) return [];
  if (!pattern) return [{ substring: str, matched: false }];

  const result = useRegex ? splitStringRegexMatch(str, pattern) : splitStringExactMatch(str, pattern);

  // Filter out empty substrings (except for edge cases where they might be meaningful)
  return result.filter((item) => item.substring.length > 0);
}

export function highlightMatchedText(text: Array<{ substring: string; matched: boolean }>, highlightClass?: string) {
  const highlightText = (content: string) => {
    return (
      <span className={highlightClass ?? ''} style={{ backgroundColor: highlightClass ? 'inherit' : 'yellow' }}>
        {content}
      </span>
    );
  };
  const highlighted = text.map((item) => (item.matched ? highlightText(item.substring) : item.substring));
  return <>{highlighted}</>;
}

/**
 * Helper function to split string using exact text matching
 */
function splitStringExactMatch(str: string, pattern: string): Array<{ substring: string; matched: boolean }> {
  const result: Array<{ substring: string; matched: boolean }> = [];
  let remaining = str;
  let index = remaining.indexOf(pattern);

  while (index !== -1) {
    // Add non-matching substring before the match
    const beforeMatch = remaining.substring(0, index);
    if (beforeMatch) {
      result.push({ substring: beforeMatch, matched: false });
    }

    // Add the matched substring
    result.push({ substring: pattern, matched: true });

    remaining = remaining.substring(index + pattern.length);
    index = remaining.indexOf(pattern);
  }

  // Add any remaining non-matching substring
  if (remaining) {
    result.push({ substring: remaining, matched: false });
  }

  return result;
}

/**
 * Helper function to split string using regex pattern matching
 */
function splitStringRegexMatch(str: string, pattern: string): Array<{ substring: string; matched: boolean }> {
  const result: Array<{ substring: string; matched: boolean }> = [];
  let regex: RegExp;

  try {
    regex = new RegExp(pattern, 'g');
  } catch (error) {
    // invalid regex can't match in the string, so no need to force error handling upstream.
    return [{ substring: str, matched: false }];
  }

  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(str)) !== null) {
    // Add non-matching substring before the match
    if (match.index > lastIndex) {
      const nonMatchSubstring = str.substring(lastIndex, match.index);
      if (nonMatchSubstring) {
        result.push({ substring: nonMatchSubstring, matched: false });
      }
    }

    // Add the matched substring
    result.push({ substring: match[0], matched: true });
    lastIndex = regex.lastIndex;

    // Prevent infinite loop for zero-length matches
    if (match[0].length === 0) {
      regex.lastIndex++;
    }
  }

  // Add any remaining non-matching substring
  if (lastIndex < str.length) {
    result.push({ substring: str.substring(lastIndex), matched: false });
  }

  return result;
}

```

---

## 5. Build & Verification Checklist

1. Recreate directory structure: `mkdir -p src/{styles,types,stores,actions,utils,assets,uikit/icons,components/{navigation,query_view,event_stream,timeseries,top_n,charts,entities,common,query_history,saved_queries,docs,bulk_actions,bulk_job_history,bulk_label_drawer,rules_visualizer}}`
2. Write every file from Section 4 at the specified path
3. Run `npm ci` to install dependencies
4. Run `npm run format:check` — all files must pass Prettier
5. Run `npm run build` — production build must succeed with no errors
6. Run `npm start` — dev server on port 5002
7. Verify in browser:
   - NavBar renders with Osprey logo and hamburger menu
   - Query panel on left (420px) with query input textarea and interval selector
   - Timeseries chart shows histogram bars (purple #8e5ea2)
   - Event Stream shows cards with action names, timestamps, feature grids
   - TopN panel shows dimension tables
   - All using dummy data from `example_data/`

---

*End of plan. Total source files: 228*
