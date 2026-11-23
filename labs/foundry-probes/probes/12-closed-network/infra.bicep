// probe 12(閉域)と 13(権限)の B1〜B5 で使う閉域の環境。
//
// 構成(Learn: configure-private-link / agents/how-to/virtual-networks / agents/environment-setup /
// agents/concepts/standard-agent-setup と、REST 仕様 cognitiveservices 2026-11-01 から自前で組んだ。
// 公式テンプレート 15-private-network-standard-agent-setup は foundry-samples が 404 で取得できない):
//   - VNet(10.40.0.0/16)
//       snet-agent 10.40.0.0/24  Microsoft.App/environments に委任。defaultOutboundAccess=false(NAT なし)
//       snet-pe    10.40.1.0/24  プライベートエンドポイント。defaultOutboundAccess=false
//       snet-vm    10.40.2.0/24  検証用 VM。defaultOutboundAccess=true(VM から ARM と公開側の
//                                アカウントを呼ぶため。エージェントサブネットとは独立)
//   - Private DNS ゾーン 6 つ(Foundry 3 つ・Search・Cosmos・Blob)を VNet にリンク
//   - standard setup の BYO: Storage(Blob)・Cosmos DB for NoSQL **Serverless**・AI Search **Basic**。
//     3 つとも publicNetworkAccess=Disabled+プライベートエンドポイント
//   - Foundry アカウント(publicNetworkAccess=Disabled、networkInjections で agent サブネットに注入)
//     +プロジェクト+接続 3 本+モデル 1 つ(GlobalStandard)
//   - ユーザー割り当て MI 5 つ(権限の検証用。Entra のユーザー・アプリは作らない)
//   - 検証用 Linux VM(B2ats v2、パブリック IP なし。テストは az vm run-command invoke で VM 内から)
//
// capability host(アカウント → プロジェクト)は作成の可否とエラーを記録したいので、
// Bicep ではなく deploy.sh から az rest で作る。
//
//   az group create -n rg-ignite26-verify -l japaneast
//   az deployment group create -g rg-ignite26-verify -f infra.bicep \
//     -p userObjectId=$(az ad signed-in-user show --query id -o tsv) sshPublicKey="$(cat <鍵>.pub)"

@description('リソース名のベース(英小文字数字。グローバル一意な名前の衝突を避けるため RG ID から作る)')
param baseName string = 'iv${take(uniqueString(resourceGroup().id), 6)}'

param location string = resourceGroup().location

@description('デプロイするモデル(japaneast の GlobalStandard で使える小さいもの)')
param modelName string = 'gpt-5.4-mini'
param modelVersion string = '2026-03-17'

@description('GlobalStandard の容量(1K TPM 単位)。容量自体は無料。1 だとツール付きの呼び出しで 429 が出るので 10')
param modelCapacity int = 10

@description('実行者(az login 中のユーザー)の objectId。外からの拒否が RBAC ではなくネットワークによることを示すため、閉域のアカウントにも Foundry User を付ける')
param userObjectId string

@description('VM の SSH 公開鍵(ログインには使わない。Linux VM の作成に資格情報が必須なため。秘密鍵はリポジトリに置かない)')
@secure()
param sshPublicKey string

param vmSize string = 'Standard_B1s' // Basv2 系はこのサブスクリプションのクォータが 0(2026-11-22 実測)

// --- ロール(GUID で指定する。名前は改名中のものがある) ---
var roles = {
  foundryUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Foundry User(旧 Azure AI User)
  projectRuntimeUser: '142bfaed-a13f-4c2d-bed2-6db62c4a1009' // Foundry Project Runtime User(rbac-foundry 未掲載)
  reader: 'acdd72a7-3385-48ef-bd42-f606fba81ae7' // Reader
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  storageBlobDataOwner: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  cosmosDbOperator: '230815da-be43-4aae-9cb4-875f7bd000aa'
  searchIndexDataContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
}

// ============================================================
// ネットワーク
// ============================================================

// Network API は 2026-03-31 より後の版(2026-05-01)。この版から新しい VNet のサブネットは既定で
// プライベート(defaultOutboundAccess=false)になる(default-outbound-access)。値は明示しておき、
// 作成後に GET で実際の値を記録する。
resource vnet 'Microsoft.Network/virtualNetworks@2026-05-01' = {
  name: 'vnet-${baseName}'
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.40.0.0/16'] }
    subnets: [
      {
        name: 'snet-agent'
        properties: {
          addressPrefix: '10.40.0.0/24'
          defaultOutboundAccess: false
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: { serviceName: 'Microsoft.App/environments' }
            }
          ]
        }
      }
      {
        name: 'snet-pe'
        properties: {
          addressPrefix: '10.40.1.0/24'
          defaultOutboundAccess: false
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'snet-vm'
        properties: {
          addressPrefix: '10.40.2.0/24'
          defaultOutboundAccess: true
        }
      }
    ]
  }
}

var agentSubnetId = '${vnet.id}/subnets/snet-agent'
var peSubnetId = '${vnet.id}/subnets/snet-pe'
var vmSubnetId = '${vnet.id}/subnets/snet-vm'

var zoneNames = {
  cognitive: 'privatelink.cognitiveservices.azure.com'
  openai: 'privatelink.openai.azure.com'
  aiservices: 'privatelink.services.ai.azure.com'
  search: 'privatelink.search.windows.net'
  cosmos: 'privatelink.documents.azure.com'
  blob: 'privatelink.blob.core.windows.net'
}

resource zones 'Microsoft.Network/privateDnsZones@2024-06-01' = [
  for z in items(zoneNames): {
    name: z.value
    location: 'global'
  }
]

resource zoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [
  for (z, i) in items(zoneNames): {
    parent: zones[i]
    name: 'link-${baseName}'
    location: 'global'
    properties: {
      registrationEnabled: false
      virtualNetwork: { id: vnet.id }
    }
  }
]

// items() はキーの昇順: aiservices(0) blob(1) cognitive(2) cosmos(3) openai(4) search(5)
var zoneIdAiServices = zones[0].id
var zoneIdBlob = zones[1].id
var zoneIdCognitive = zones[2].id
var zoneIdCosmos = zones[3].id
var zoneIdOpenai = zones[4].id
var zoneIdSearch = zones[5].id

// ============================================================
// standard setup の BYO リソース(3 つとも公開アクセス無効)
// ============================================================

resource storage 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: 'st${baseName}'
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
      virtualNetworkRules: []
      ipRules: []
    }
  }
}

// Cosmos DB for NoSQL を Serverless で(standard-agent-setup は「Provisioned Throughput と Serverless の
// 両方に対応」と書く。プロビジョンだと 3,000 RU/s 以上で常時課金)
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: 'cos-${baseName}'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [{ name: 'EnableServerless' }]
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [{ locationName: location, failoverPriority: 0, isZoneRedundant: false }]
    publicNetworkAccess: 'Disabled'
    disableLocalAuth: true
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    enableFreeTier: false
  }
}

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: 'srch-${baseName}'
  location: location
  sku: { name: 'basic' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'Default'
    publicNetworkAccess: 'disabled'
    disableLocalAuth: false
    authOptions: { aadOrApiKey: { aadAuthFailureMode: 'http401WithBearerChallenge' } }
    networkRuleSet: { bypass: 'None', ipRules: [] }
    semanticSearch: 'disabled'
  }
}

// ============================================================
// Foundry アカウント(閉域)+プロジェクト
// ============================================================

resource foundry 'Microsoft.CognitiveServices/accounts@2026-11-01' = {
  name: 'aif-${baseName}'
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: 'aif-${baseName}'
    allowProjectManagement: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
      ipRules: []
      virtualNetworkRules: []
    }
    // 13 の B2(API キーの届く範囲)を閉域でも見るため、キー認証は有効のまま作る
    disableLocalAuth: false
    // 作成時にしか入れられない(Learn)。仕様上は x-ms-mutability の指定なし
    networkInjections: [
      {
        scenario: 'agent'
        subnetArmId: agentSubnetId
        useMicrosoftManagedNetwork: false
      }
    ]
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2026-11-01' = {
  parent: foundry
  name: 'proj'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'ignite26 closed-network verify'
    description: 'probe 12/13: PNA Disabled + BYO VNet + standard setup (Cosmos Serverless)'
  }
}

// 接続(capability host が名前で参照する)。アカウント配下のサブリソース操作は直列にする
resource connCosmos 'Microsoft.CognitiveServices/accounts/projects/connections@2026-11-01' = {
  parent: project
  name: 'conn-cosmos'
  properties: {
    category: 'CosmosDb'
    target: cosmos.properties.documentEndpoint
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: cosmos.id
      location: location
    }
  }
}

resource connStorage 'Microsoft.CognitiveServices/accounts/projects/connections@2026-11-01' = {
  parent: project
  name: 'conn-storage'
  dependsOn: [connCosmos]
  properties: {
    category: 'AzureStorageAccount'
    target: storage.properties.primaryEndpoints.blob
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: storage.id
      location: location
    }
  }
}

resource connSearch 'Microsoft.CognitiveServices/accounts/projects/connections@2026-11-01' = {
  parent: project
  name: 'conn-search'
  dependsOn: [connStorage]
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${search.name}.search.windows.net'
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: search.id
      location: location
    }
  }
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2026-11-01' = {
  parent: foundry
  name: modelName
  dependsOn: [connSearch]
  sku: {
    name: 'GlobalStandard'
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

// ============================================================
// プライベートエンドポイント 4 本
// ============================================================

resource peFoundry 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: 'pe-${baseName}-aif'
  location: location
  properties: {
    subnet: { id: peSubnetId }
    privateLinkServiceConnections: [
      {
        name: 'aif'
        properties: { privateLinkServiceId: foundry.id, groupIds: ['account'] }
      }
    ]
  }
}

resource peFoundryDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: peFoundry
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      { name: 'cognitive', properties: { privateDnsZoneId: zoneIdCognitive } }
      { name: 'openai', properties: { privateDnsZoneId: zoneIdOpenai } }
      { name: 'aiservices', properties: { privateDnsZoneId: zoneIdAiServices } }
    ]
  }
}

resource peStorage 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: 'pe-${baseName}-blob'
  location: location
  properties: {
    subnet: { id: peSubnetId }
    privateLinkServiceConnections: [
      {
        name: 'blob'
        properties: { privateLinkServiceId: storage.id, groupIds: ['blob'] }
      }
    ]
  }
}

resource peStorageDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: peStorage
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [{ name: 'blob', properties: { privateDnsZoneId: zoneIdBlob } }]
  }
}

resource peCosmos 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: 'pe-${baseName}-cosmos'
  location: location
  properties: {
    subnet: { id: peSubnetId }
    privateLinkServiceConnections: [
      {
        name: 'cosmos'
        properties: { privateLinkServiceId: cosmos.id, groupIds: ['Sql'] }
      }
    ]
  }
}

resource peCosmosDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: peCosmos
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [{ name: 'cosmos', properties: { privateDnsZoneId: zoneIdCosmos } }]
  }
}

resource peSearch 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: 'pe-${baseName}-search'
  location: location
  properties: {
    subnet: { id: peSubnetId }
    privateLinkServiceConnections: [
      {
        name: 'search'
        properties: { privateLinkServiceId: search.id, groupIds: ['searchService'] }
      }
    ]
  }
}

resource peSearchDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: peSearch
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [{ name: 'search', properties: { privateDnsZoneId: zoneIdSearch } }]
  }
}

// ============================================================
// プロジェクト MI のデータロール(standard setup の実行時。capability host 作成前に付ける)
// ============================================================

resource raStorageContrib 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, project.id, roles.storageBlobDataContributor)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataContributor)
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource raStorageOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, project.id, roles.storageBlobDataOwner)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataOwner)
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource raCosmosOperator 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cosmos.id, project.id, roles.cosmosDbOperator)
  scope: cosmos
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cosmosDbOperator)
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB のデータプレーン(Built-in Data Contributor)。テンプレートはコンテナー単位に付けるが、
// コンテナーは capability host が作るので、ここではアカウント全体に付ける
resource cosmosDataContrib 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  parent: cosmos
  name: guid(cosmos.id, project.id, 'cosmos-data-contributor')
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: project.identity.principalId
    scope: cosmos.id
  }
}

resource raSearchIndex 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, project.id, roles.searchIndexDataContributor)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexDataContributor)
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource raSearchService 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, project.id, roles.searchServiceContributor)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchServiceContributor)
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// 実行者(外からの拒否がネットワーク由来であることを示すため)
resource raUserFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, userObjectId, roles.foundryUser)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.foundryUser)
    principalId: userObjectId
    principalType: 'User'
  }
}

// ============================================================
// 権限検証用のユーザー割り当て MI(13)
//   id-ops: Foundry User @アカウント(VM 内の操作役。アカウントスコープの対照も兼ねる)
//   id-fu : Foundry User @プロジェクト(B5 で Foundry Project Manager @アカウントを足す)
//   id-rt : Foundry Project Runtime User @プロジェクト(B5 で Foundry Account Owner @アカウントを足す)
//   id-ac1: Foundry Agent Consumer @エージェント(エージェント作成後に CLI で付ける)
//   id-rd : Reader @アカウント(B3 で 2 人目の Agent Consumer @エージェントを足す)
// ============================================================

var idNames = ['id-ops', 'id-fu', 'id-rt', 'id-ac1', 'id-rd']

resource ids 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = [
  for n in idNames: {
    name: '${n}-${baseName}'
    location: location
  }
]

resource raOps 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, ids[0].id, roles.foundryUser)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.foundryUser)
    principalId: ids[0].properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource raFuProj 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, ids[1].id, roles.foundryUser)
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.foundryUser)
    principalId: ids[1].properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource raRtProj 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(project.id, ids[2].id, roles.projectRuntimeUser)
  scope: project
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.projectRuntimeUser)
    principalId: ids[2].properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource raRdAcct 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, ids[4].id, roles.reader)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.reader)
    principalId: ids[4].properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ============================================================
// 検証用 VM(パブリック IP なし・Bastion なし)
// ============================================================

resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: 'nic-${baseName}-vm'
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: { id: vmSubnetId }
          privateIPAllocationMethod: 'Static'
          privateIPAddress: '10.40.2.10'
        }
      }
    ]
  }
}

resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: 'vm-${baseName}'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${ids[0].id}': {}
      '${ids[1].id}': {}
      '${ids[2].id}': {}
      '${ids[3].id}': {}
      '${ids[4].id}': {}
    }
  }
  properties: {
    hardwareProfile: { vmSize: vmSize }
    osProfile: {
      computerName: 'vm-probe'
      adminUsername: 'probe'
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: {
          publicKeys: [{ path: '/home/probe/.ssh/authorized_keys', keyData: sshPublicKey }]
        }
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        deleteOption: 'Delete'
        diskSizeGB: 30
        managedDisk: { storageAccountType: 'Standard_LRS' }
      }
    }
    networkProfile: {
      networkInterfaces: [{ id: nic.id, properties: { deleteOption: 'Delete' } }]
    }
    diagnosticsProfile: { bootDiagnostics: { enabled: false } }
  }
}

// ============================================================
// 出力
// ============================================================

output baseName string = baseName
output foundryName string = foundry.name
output foundryId string = foundry.id
output projectName string = project.name
output projectId string = project.id
output projectPrincipalId string = project.identity.principalId
output accountPrincipalId string = foundry.identity.principalId
output projectEndpoint string = 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com/api/projects/${project.name}'
output accountEndpoint string = 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com'
output openaiV1Endpoint string = 'https://${foundry.properties.customSubDomainName}.openai.azure.com/openai/v1'
output modelDeploymentName string = modelDeployment.name
output vmName string = vm.name
output vmPrivateIp string = '10.40.2.10'
output vnetId string = vnet.id
output identities array = [
  for (n, i) in idNames: {
    name: n
    resourceName: ids[i].name
    clientId: ids[i].properties.clientId
    principalId: ids[i].properties.principalId
    id: ids[i].id
  }
]
output connections array = [connCosmos.name, connStorage.name, connSearch.name]
