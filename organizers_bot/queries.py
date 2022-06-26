login_query = """
            mutation Login($login: String!, $password: String!) {  
                login(input: {
                    login: $login, 
                    password: $password
                }) {    
                    jwt    
                }
            }
            """

get_team = """
            query getTeam {
                profiles {
                    nodes {
                        ...ProfileFragment 
                    }    
                }
            }
            fragment ProfileFragment on Profile {
                id  username  color  description  role  
            }
            """

get_me = """
    query Me {
      me {
        ...ProfileFragment
      }
    }
    fragment ProfileFragment on Profile {
      id
      username
      color
      description
      role
      nodeId
    }
    """

import_ctf = """
            mutation importctf($id: Int!) {
                importCtf(input: {ctftimeId: $id}) {    
                    ctf {   
                        ...CtfFragment
                    }
                }
            }
            fragment CtfFragment on Ctf {  
                  id  granted  ctfUrl  ctftimeUrl  description  endTime
                logoUrl  startTime  weight  title
            }
            """

create_ctf = """
    mutation createCtf(
    $title: String!, 
    $startTime: Datetime!,
    $endTime: Datetime!,
    $weight: Float,
    $ctfUrl: String,
    $ctftimeUrl: String,
    $logoUrl: String, $description: String) {  
        createCtf(input: {
            ctf: {
                title: $title, 
                weight: $weight, 
                ctfUrl: $ctfUrl, 
                ctftimeUrl: $ctftimeUrl, 
                logoUrl: $logoUrl, 
                startTime: $startTime, 
                endTime: $endTime, 
                description: $description
            }
        }){
            ctf {
                ...CtfFragment  
            } 
        }
    }

    fragment CtfFragment on Ctf {  
        nodeId  id  granted  ctfUrl  ctftimeUrl  description  endTime  
        logoUrl  startTime  weight  title  
    }
    """

get_ctfs = """
            query Ctfs {
                ctfs {
                    nodes {
                        ...CtfFragment
                    }
                }
            }
            fragment CtfFragment on Ctf {  
                  id  granted  ctfUrl  ctftimeUrl  description  endTime
                logoUrl  startTime  weight  title
            }"""

get_past_ctfs = """
            query PastCtfs($first: Int, $offset: Int) {  
                pastCtf(first: $first, offset: $offset) {    
                    nodes {      
                        ...CtfFragment    
                    }
                    totalCount  
                }
            }
            fragment CtfFragment on Ctf {  
                  id  granted ctfUrl  ctftimeUrl  
                description endTime  logoUrl  startTime  
                weight title
            }"""

get_incoming_ctfs = """
            query IncomingCtfs {  
                incomingCtf {    
                    nodes {      
                        ...CtfFragment    
                    }  
                }
            }
            fragment CtfFragment on Ctf {  
                  id  granted  ctfUrl  ctftimeUrl  description  endTime
                logoUrl  startTime  weight  title
            }"""

get_full_ctf = """
            query GetFullCtf($id: Int!) {
                ctf(id: $id) {
                    ...FullCtfFragment
                    }
                }
                fragment FullCtfFragment on Ctf {  
                    ...CtfFragment  

                    tasks {
                        nodes {
                            ...TaskFragment
                        }
                    }

                    secrets {    
                        ...CtfSecretFragment
                    }

                    invitations {    
                        nodes {      
                            ...InvitationFragment
                        }
                    } 
                }

                fragment CtfFragment on Ctf {  
                      id  granted  ctfUrl  ctftimeUrl  description  
                    endTime  logoUrl  startTime  weight  title
                }

                fragment TaskFragment on Task {  
                      id  title  ctfId  padUrl  description  flag  
                    solved  category  workOnTasks {    
                        nodes {      
                            ...WorkingOnFragment
                        }
                    }
                }

                fragment WorkingOnFragment on WorkOnTask {  
                      profileId  profile {    
                        ...ProfileFragment
                    }
                }

                fragment ProfileFragment on Profile {  
                    id  username  color  description  role  
                }

                fragment CtfSecretFragment on CtfSecret {  
                      credentials
                }

                fragment InvitationFragment on Invitation {  
                      ctfId  profileId
                }"""

create_task = """
            mutation createTaskForCtfId(
            $ctfId: Int!, $title: String!, $category: String, $description: String, $flag: String) { 
                createTask(input: {
                    ctfId: $ctfId, title: $title, category: $category, 
                    description: $description, flag: $flag
                }) {
                    task {
                        ...TaskFragment
                    }
                }
            }

            fragment TaskFragment on Task {  
                  id  title  ctfId  padUrl  description  flag
                solved  category  workOnTasks {   
                    nodes { 
                        ...WorkingOnFragment
                    }
                }
            }

            fragment WorkingOnFragment on WorkOnTask { 
                  profileId  profile {    
                    ...ProfileFragment    
                }  
            }

            fragment ProfileFragment on Profile { 
                id  username  color  description  role    
            }"""

delete_task = """mutation deleteTask($id: Int!) {
    deleteTask(input: {id: $id}) {
        deletedTaskNodeId
    }
    }"""

update_task = """mutation updateTask(
    $id: Int!, $title: String, $description: String, 
    $category: String, $flag: String) {  
        updateTask(input: {
            id: $id,
            patch: {
                title: $title, 
                category: 
                $category, 
                description: $description, 
                flag: $flag
            }
        }) 
        {
            task {
                ...TaskFragment
            }
        }
    }

    fragment TaskFragment on Task {  
          id  title  ctfId  padUrl  description flag  
        solved  category  workOnTasks { 
            nodes { 
                ...WorkingOnFragment
            }      
        } 
    }

    fragment WorkingOnFragment on WorkOnTask {
          profileId  profile {
            ...ProfileFragment    
        }  
    }

    fragment ProfileFragment on Profile { 
        id  username  color description  role    
    }"""

create_account = """mutation createInvitationToken($role: Role!) {  
    createInvitationLink(input: {role: $role}) {
        invitationLinkResponse {
            token
        }
    }
}"""

register_with_token = """mutation RegisterWithToken(
    $login: String!, $password: String!, $token: String!) {
        registerWithToken(input: {
            login: $login, 
            password: $password, 
            token: $token
        }) 
        {    
            jwt 
        }
    }"""

start_working_on = """mutation startWorkingOn($taskId: Int!) {
    startWorkingOn(input: {
        taskId: $taskId}) {
            task {
                ...TaskFragment          
            }      
        }
    }

    fragment TaskFragment on Task {  
          id  title  ctfId  padUrl  description  flag  solved  
        category  workOnTasks {    
            nodes {
                ...WorkingOnFragment          
            }      
        }  
    }

    fragment WorkingOnFragment on WorkOnTask {  
          profileId  profile {    
            ...ProfileFragment      
        }  
    }

    fragment ProfileFragment on Profile {  
        id  username  color  description  role    
    }"""



assign_user = """
mutation assignUserToTask($taskId: Int!, $userId: Int!) {
  assignUserToTask(input: {taskId: $taskId, userId: $userId}) {
    task {
      ...TaskFragment
      __typename
    }
    __typename
  }
}

fragment TaskFragment on Task {
  nodeId
  id
  title
  ctfId
  padUrl
  description
  flag
  solved
  category
  workOnTasks {
    nodes {
      ...WorkingOnFragment
      __typename
    }
    __typename
  }
  __typename
}

fragment WorkingOnFragment on WorkOnTask {
  nodeId
  profileId
  profile {
    ...ProfileFragment
    __typename
  }
  __typename
}

fragment ProfileFragment on Profile {
  id
  username
  color
  description
  role
  nodeId
  __typename
}
"""

unassign_user = """
mutation unassignUserFromTask($taskId: Int!, $userId: Int!) {
  unassignUserFromTask(input: {taskId: $taskId, userId: $userId}) {
    task {
      ...TaskFragment
      __typename
    }
    __typename
  }
}

fragment TaskFragment on Task {
  nodeId
  id
  title
  ctfId
  padUrl
  description
  flag
  solved
  category
  workOnTasks {
    nodes {
      ...WorkingOnFragment
      __typename
    }
    __typename
  }
  __typename
}

fragment WorkingOnFragment on WorkOnTask {
  nodeId
  profileId
  profile {
    ...ProfileFragment
    __typename
  }
  __typename
}

fragment ProfileFragment on Profile {
  id
  username
  color
  description
  role
  nodeId
  __typename
}
"""

stop_working_on = """mutation stopWorkingOn($taskId: Int!) {
    stopWorkingOn(input: {
        taskId: $taskId}) {
            task {
                ...TaskFragment          
            }      
        }
    }

    fragment TaskFragment on Task {  
          id  title  ctfId  padUrl  description  flag  solved  
        category  workOnTasks {    
            nodes {
                ...WorkingOnFragment          
            }      
        }  
    }

    fragment WorkingOnFragment on WorkOnTask {  
          profileId  profile {    
            ...ProfileFragment      
        }  
    }

    fragment ProfileFragment on Profile {  
        id  username  color  description  role    
    }"""

new_token = """query newToken { newToken }"""

subscribe_flags = """subscription subscribeToFlag {  
    listen(topic:"task-solved:tasks") {
        relatedNodeId    relatedNode {
            ... on Task {
                ...TaskFragment
            }
        }    
    }
}

fragment TaskFragment on Task {
      id  title  ctfId  padUrl  description flag  solved  category  
    workOnTasks {    
        nodes {
            ...WorkingOnFragment
        }      
    }
}

fragment WorkingOnFragment on WorkOnTask {  
      profileId  profile {    
        ...ProfileFragment
    }
}

fragment ProfileFragment on Profile {  
    id  username  color description  role    
}"""

subscribe_to_ctf_created = """
    subscription subscribeToCtfCreated {
      listen(topic: "created:ctfs") {
        relatedNodeId
        relatedNode {
          ... on Ctf {
            ...CtfFragment
          }
        }
      }
    }

    fragment CtfFragment on Ctf {
        nodeId id granted ctfUrl ctftimeUrl description endTime 
        logoUrl startTime weight title 
    }
    """
subscribe_to_ctf_deleted = """
    subscription subscribeToCtfDeleted {
      listen(topic: "deleted:ctfs") {
        relatedNodeId
        relatedNode {
          ... on Ctf {
            ...CtfFragment
          }
        }
      }
    }
 
    fragment CtfFragment on Ctf {
        nodeId id granted ctfUrl ctftimeUrl description endTime 
        logoUrl startTime weight title 
    }
    """

subscribe_to_ctf = """
    subscription subscribeToCtf {
      listen(topic: "update:ctfs") {
        relatedNodeId
        relatedNode {
          nodeId
          ... on Ctf {
            ...FullCtfFragment
          }
        }
      }
    }
    fragment FullCtfFragment on Ctf {
      ...CtfFragment

      tasks {
        nodes {
          ...TaskFragment
        }
      }

      secrets {
        ...CtfSecretFragment
      }

      invitations {
        nodes {
          ...InvitationFragment
        }
      }
    }

    fragment ProfileFragment on Profile {
      id
      username
      color
      description
      role
      nodeId
    }

    fragment WorkingOnFragment on WorkOnTask {
      nodeId
      profileId
      profile {
        ...ProfileFragment
      }
    }

    fragment CtfSecretFragment on CtfSecret {
      nodeId
      credentials
    }

    fragment InvitationFragment on Invitation {
      nodeId
      ctfId
      profileId
    }

    fragment TaskFragment on Task {
      nodeId
      id
      title
      ctfId
      padUrl
      description
      flag
      solved
      category
      workOnTasks {
        nodes {
          ...WorkingOnFragment
        }
      }
    }

    fragment CtfFragment on Ctf {
        nodeId id granted ctfUrl ctftimeUrl description endTime 
        logoUrl startTime weight title 
    }
    """

subscribe_to_task = """
    subscription subscribeToTask {
      listen(topic: "update:tasks") {
        relatedNode {
          nodeId
          ... on Task {
            ...TaskFragment
          }
        }
      }
    }
    fragment WorkingOnFragment on WorkOnTask {
      nodeId
      profileId
      profile {
        ...ProfileFragment
      }
    }

    fragment TaskFragment on Task {
      nodeId
      id
      title
      ctfId
      padUrl
      description
      flag
      solved
      category
      workOnTasks {
        nodes {
          ...WorkingOnFragment
        }
      }
    }
    fragment ProfileFragment on Profile {
      id
      username
      color
      description
      role
      nodeId
    }
    """

get_users = """
query getUsers {
  users {
    nodes {
      ...UserFragment
    }
  }
}

fragment UserFragment on User {
   login role id
  profile {
    ...ProfileFragment
  }
}

fragment ProfileFragment on Profile {
  id username color description role 
}
"""

