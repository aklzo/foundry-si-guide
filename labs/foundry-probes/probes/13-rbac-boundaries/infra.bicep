// probe 13 の B2(API キー・disableLocalAuth の反映時間)と B6(Memory)、probe 14(Agent Optimizer)で使う
// パブリックの basic 構成。Memory は閉域で非対応(what-is-memory)なので、閉域の環境とは別に作る。
// アカウント自体に固定費はない。12 の infra.bicep と同じ RG に置き、12 が作った UAMI を参照する。
//
//   az deployment group create -g rg-ignite26-verify -f infra.bicep \
//     -p userObjectId=$(az ad signed-in-user show --query id -o tsv) baseName=<12 の baseName>

@description('12 の infra.bicep と同じ baseName(UAMI の名前に使っている)')
param baseName string

param location string = resourceGroup().location

param userObjectId string

@description('エージェント・評価用の小さいモデル')
param chatModel string = 'gpt-5.4-mini'
param chatVersion string = '2026-03-17'

@description('Agent Optimizer の最適化モデル(対応: gpt-5 / 5.1 / 5.2 / 5.4 / 5.5 / DeepSeek-V4-Pro / DeepSeek-V-3.2)')
param optModel string = 'gpt-5.4'
param optVersion string = '2026-03-05'

@description('Memory の埋め込みモデル')
param embModel string = 'text-embedding-3-small'
param embVersion string = '1'

var foundryUser = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

resource foundry 'Microsoft.CognitiveServices/accounts@2026-11-01' = {
  name: 'aif-${baseName}p'
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: 'aif-${baseName}p'
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2026-11-01' = {
  parent: foundry
  name: 'pub'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'ignite26 public basic verify'
    description: 'probe 13 (B2/B6) / 14: public basic setup'
  }
}

resource depChat 'Microsoft.CognitiveServices/accounts/deployments@2026-11-01' = {
  parent: foundry
  name: chatModel
  dependsOn: [project]
  sku: { name: 'GlobalStandard', capacity: 10 }
  properties: {
    model: { format: 'OpenAI', name: chatModel, version: chatVersion }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource depOpt 'Microsoft.CognitiveServices/accounts/deployments@2026-11-01' = {
  parent: foundry
  name: optModel
  dependsOn: [depChat]
  sku: { name: 'GlobalStandard', capacity: 10 }
  properties: {
    model: { format: 'OpenAI', name: optModel, version: optVersion }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource depEmb 'Microsoft.CognitiveServices/accounts/deployments@2026-11-01' = {
  parent: foundry
  name: embModel
  dependsOn: [depOpt]
  sku: { name: 'GlobalStandard', capacity: 10 }
  properties: {
    model: { format: 'OpenAI', name: embModel, version: embVersion }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource idOps 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'id-ops-${baseName}'
}

// 実行者・id-ops(VM から公開側を呼ぶ操作役)・プロジェクト MI(Memory と評価がモデルを呼ぶ)に Foundry User @アカウント
resource raUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, userObjectId, foundryUser)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUser)
    principalId: userObjectId
    principalType: 'User'
  }
}

resource raOps 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, idOps.id, foundryUser)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUser)
    principalId: idOps.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource raProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, project.id, foundryUser)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUser)
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output foundryName string = foundry.name
output foundryId string = foundry.id
output projectId string = project.id
output projectEndpoint string = 'https://${foundry.properties.customSubDomainName}.services.ai.azure.com/api/projects/${project.name}'
output openaiV1Endpoint string = 'https://${foundry.properties.customSubDomainName}.openai.azure.com/openai/v1'
output chatDeployment string = depChat.name
output optDeployment string = depOpt.name
output embDeployment string = depEmb.name
